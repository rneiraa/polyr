"""Sistema de expresiones perezosas: el equivalente de rlang.

``f.x > 1`` no calcula nada al escribirse: construye un árbol de nodos
(:class:`Expr`) que un verbo compila más tarde contra un data frame concreto.

La compilación recibe un :class:`EvalContext` que conoce el esquema (los
tipos) de la *data mask*. Así, cada nodo puede aplicar las reglas de tipos de
:mod:`polyr._types` antes de ejecutar nada, igual que dplyr/vctrs.

Los valores de Python que aparecen dentro de una expresión (``f.x > limite``)
se capturan al construirla, lo que equivale a ``.env$limite`` en dplyr: no
hay ambigüedad posible entre columnas y variables del entorno.
"""
from __future__ import annotations

import operator
from typing import Any, Callable, Sequence

import polars as pl


_SCALARS = (int, float, str, bool, type(None))

_BINOPS: dict[str, Callable[[Any, Any], Any]] = {
    "==": operator.eq, "!=": operator.ne,
    "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge,
    "+": operator.add, "-": operator.sub, "*": operator.mul,
    "/": operator.truediv, "//": operator.floordiv, "%": operator.mod,
    "**": operator.pow, "&": operator.and_, "|": operator.or_,
}
_UNARYOPS: dict[str, Callable[[Any], Any]] = {"~": operator.invert, "-": operator.neg}


class EvalContext:
    """Información disponible al compilar una expresión.

    * ``schema``: tipos de la data mask, para aplicar las reglas de vctrs.
    * ``data``: el data frame completo, para helpers que necesitan resolver
      selecciones en tiempo de compilación (``if_any``, ``if_all``, ``pick``).
    * ``groups``: variables de agrupación, que esos mismos helpers excluyen
      de sus selecciones (como hace ``across()``).
    """

    def __init__(self, schema: pl.Schema | dict[str, pl.DataType],
                 data: pl.DataFrame | None = None,
                 groups: Sequence[str] = ()):
        self.schema = pl.Schema(schema)
        self.data = data
        self.groups = tuple(groups)

    def dtype(self, e: pl.Expr) -> pl.DataType:
        """Tipo resultante de una expresión de polars, sin evaluar datos."""
        lf = pl.LazyFrame(schema=self.schema)
        return lf.select(e.alias("__dtype__")).collect_schema()["__dtype__"]


class Expr:
    """Nodo base del árbol de expresiones."""

    __hash__ = None  # type: ignore[assignment]  # == está sobrecargado

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        raise NotImplementedError

    def columns(self) -> set[str]:
        """Columnas referenciadas (para validarlas antes de evaluar)."""
        raise NotImplementedError

    # Python no permite sobrecargar and/or/not: fallar con un mensaje útil es
    # mejor que devolver en silencio un resultado incorrecto.
    def __bool__(self) -> bool:
        raise TypeError(
            f"La expresión `{self!r}` no tiene un valor de verdad.\n"
            "ℹ Usa `&`, `|` y `~` en lugar de `and`, `or` y `not`, y pon cada "
            "comparación entre paréntesis: (f.x > 1) & (f.y < 2).\n"
            "ℹ Las comparaciones encadenadas (1 < f.x < 5) no están soportadas: "
            "usa (f.x > 1) & (f.x < 5)."
        )

    def _bin(self, op: str, other: Any, reverse: bool = False) -> "BinOp":
        other = wrap(other)
        return BinOp(op, other, self) if reverse else BinOp(op, self, other)

    # comparaciones (los casos invertidos, como 1 < f.x, los resuelve Python)
    def __eq__(self, o): return self._bin("==", o)  # type: ignore[override]
    def __ne__(self, o): return self._bin("!=", o)  # type: ignore[override]
    def __lt__(self, o): return self._bin("<", o)
    def __le__(self, o): return self._bin("<=", o)
    def __gt__(self, o): return self._bin(">", o)
    def __ge__(self, o): return self._bin(">=", o)

    # aritmética
    def __add__(self, o): return self._bin("+", o)
    def __radd__(self, o): return self._bin("+", o, reverse=True)
    def __sub__(self, o): return self._bin("-", o)
    def __rsub__(self, o): return self._bin("-", o, reverse=True)
    def __mul__(self, o): return self._bin("*", o)
    def __rmul__(self, o): return self._bin("*", o, reverse=True)
    def __truediv__(self, o): return self._bin("/", o)
    def __rtruediv__(self, o): return self._bin("/", o, reverse=True)
    def __floordiv__(self, o): return self._bin("//", o)
    def __rfloordiv__(self, o): return self._bin("//", o, reverse=True)
    def __mod__(self, o): return self._bin("%", o)
    def __rmod__(self, o): return self._bin("%", o, reverse=True)
    def __pow__(self, o): return self._bin("**", o)
    def __rpow__(self, o): return self._bin("**", o, reverse=True)
    def __neg__(self): return UnaryOp("-", self)

    # lógica
    def __and__(self, o): return self._bin("&", o)
    def __rand__(self, o): return self._bin("&", o, reverse=True)
    def __or__(self, o): return self._bin("|", o)
    def __ror__(self, o): return self._bin("|", o, reverse=True)
    def __invert__(self): return UnaryOp("~", self)


class Col(Expr):
    """Referencia a una columna de la data mask."""

    def __init__(self, name: str):
        self.name = name

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        return pl.col(self.name)

    def columns(self) -> set[str]:
        return {self.name}

    def __repr__(self) -> str:
        return self.name if self.name.isidentifier() else f"`{self.name}`"


class Lit(Expr):
    """Valor escalar constante."""

    def __init__(self, value: Any):
        self.value = value

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        return pl.lit(self.value)

    def columns(self) -> set[str]:
        return set()

    def __repr__(self) -> str:
        return "NA" if self.value is None else repr(self.value)


class Values(Expr):
    """Vector constante (una lista, tupla o Series de polars)."""

    def __init__(self, values: Any):
        self.values = values if isinstance(values, pl.Series) else pl.Series(list(values))

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        return pl.lit(self.values)

    def columns(self) -> set[str]:
        return set()

    def __repr__(self) -> str:
        if len(self.values) <= 5:
            return "[" + ", ".join(repr(v) for v in self.values.to_list()) + "]"
        return f"<vector de tamaño {len(self.values)}>"


class BinOp(Expr):
    def __init__(self, op: str, left: Expr, right: Expr):
        self.op, self.left, self.right = op, left, right

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        left, right = self.left.to_polars(ctx), self.right.to_polars(ctx)
        if self.op == "**":
            # En R, `^` siempre devuelve double (2L^2L es 4, no 4L).
            left = left.cast(pl.Float64)
        return _BINOPS[self.op](left, right)

    def columns(self) -> set[str]:
        return self.left.columns() | self.right.columns()

    def __repr__(self) -> str:
        return f"{_paren(self.left)} {self.op} {_paren(self.right)}"


class UnaryOp(Expr):
    def __init__(self, op: str, operand: Expr):
        self.op, self.operand = op, operand

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        return _UNARYOPS[self.op](self.operand.to_polars(ctx))

    def columns(self) -> set[str]:
        return self.operand.columns()

    def __repr__(self) -> str:
        return f"{self.op}{_paren(self.operand)}"


class Call(Expr):
    """Llamada a una función del paquete, p. ej. ``mean(f.x)``.

    ``compile_fn(ctx, *args_compilados)`` recibe el contexto para poder
    consultar tipos y aplicar las reglas de vctrs.
    """

    def __init__(self, name: str, compile_fn: Callable[..., pl.Expr],
                 args: list[Expr], extra_repr: str = ""):
        self.name, self.compile_fn, self.args, self.extra_repr = name, compile_fn, args, extra_repr

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        return self.compile_fn(ctx, *(a.to_polars(ctx) for a in self.args))

    def columns(self) -> set[str]:
        return set().union(*(a.columns() for a in self.args))

    def __repr__(self) -> str:
        parts = [repr(a) for a in self.args] + ([self.extra_repr] if self.extra_repr else [])
        return f"{self.name}({', '.join(parts)})"


def _paren(e: Expr) -> str:
    return f"({e!r})" if isinstance(e, BinOp) else repr(e)


def wrap(value: Any) -> Expr:
    """Convierte un valor de Python en un nodo de expresión."""
    if isinstance(value, Expr):
        return value
    if isinstance(value, _SCALARS):
        return Lit(value)
    if isinstance(value, (list, tuple, pl.Series)):
        return Values(value)
    raise TypeError(
        f"No se puede usar un objeto de tipo `{type(value).__name__}` dentro de una expresión."
    )


class _ColumnNamespace:
    """Punto de entrada para referenciar columnas.

    * ``f.x`` — la columna ``x``.
    * ``f["mi columna"]`` — nombres que no son identificadores válidos.
    * ``f["a":"c"]`` — rango de columnas, como ``a:c`` en R (solo en selecciones).
    """

    def __getattr__(self, name: str) -> Col:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return Col(name)

    def __getitem__(self, key: str | slice) -> Expr:
        if isinstance(key, slice):
            from .tidyselect import col_range
            if key.step is not None:
                raise TypeError("Los rangos de columnas no admiten paso: usa f['a':'c'].")
            return col_range(key.start, key.stop)
        if not isinstance(key, str):
            raise TypeError("Los nombres de columna deben ser strings.")
        return Col(key)

    def __repr__(self) -> str:
        return "<f: referencia a columnas>"


f = _ColumnNamespace()

#: Valor faltante explícito. ``mutate(z=NA)`` crea una columna de NA, mientras
#: que ``mutate(z=None)`` elimina ``z`` (como ``z = NULL`` en dplyr).
NA = Lit(None)

