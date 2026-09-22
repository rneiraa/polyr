"""Aplicar funciones a varias columnas: ``across()``, ``if_any()``, ``if_all()``.

Las funciones reciben una referencia a la columna (un :class:`~polyr.expr.Expr`)
y devuelven una expresión::

    mutate(df, across(starts_with("x"), lambda c: c * 100))
    summarise(df, across(where(is_numeric), {"media": mean, "max": max}))
    filter(df, if_any(starts_with("x"), lambda c: c > 0))

``pick()`` no aplica ninguna función: entrega las columnas seleccionadas como
un solo valor, para las funciones que trabajan sobre varias a la vez::

    mutate(df, orden=dense_rank(pick(f.apellido, f.nombre)))
"""
from __future__ import annotations

import operator
from functools import reduce
from typing import Any, Callable, Mapping, Sequence

import polars as pl

from ._types import kind, type_name
from .errors import ExprError
from .expr import Col, EvalContext, Expr, wrap
from .tidyselect import everything, resolve

__all__ = ["across", "if_any", "if_all", "pick", "Across"]

Fns = Callable[[Expr], Any] | Mapping[str, Callable[[Expr], Any]]


def _normalize_fns(fns: Fns, who: str) -> list[tuple[str | None, Callable[[Expr], Any]]]:
    if callable(fns):
        return [(None, fns)]
    if isinstance(fns, Mapping) and fns and all(callable(v) for v in fns.values()):
        return [(str(k), v) for k, v in fns.items()]
    raise TypeError(f"`{who}()` necesita una función o un diccionario {{nombre: función}}.")


class Across:
    """Resultado de :func:`across`: se expande a varias columnas dentro de un verbo."""

    def __init__(self, cols: Any, fns: Fns, names: str | None):
        self.cols = cols
        self.fns = _normalize_fns(fns, "across")
        single = len(self.fns) == 1 and self.fns[0][0] is None
        self.names = names or ("{col}" if single else "{col}_{fn}")

    def expand(self, data: pl.DataFrame, exclude: Sequence[str] = ()) -> list[tuple[str, Expr]]:
        """Pares ``(nombre, expresión)`` para las columnas seleccionadas.

        Las columnas de agrupación se excluyen, como en dplyr.
        """
        cols = [c for c in resolve(self.cols, data) if c not in set(exclude)]
        out: list[tuple[str, Expr]] = []
        for col in cols:
            for fname, fn in self.fns:
                try:
                    name = self.names.format(col=col, fn=fname or "1")
                except KeyError as err:
                    raise ExprError(
                        f"`names` solo admite los campos {{col}} y {{fn}}, no {{{err.args[0]}}}."
                    ) from err
                out.append((name, wrap(fn(Col(col)))))
        names = [n for n, _ in out]
        dup = next((n for n in names if names.count(n) > 1), None)
        if dup is not None:
            raise ExprError(f"`across()` produjo el nombre `{dup}` más de una vez.\n"
                            "ℹ Usa `names=` para generar nombres únicos.")
        return out

    def __repr__(self) -> str:
        return f"across({self.cols!r}, ...)"


def across(cols: Any = None, fns: Fns | None = None, names: str | None = None) -> Across:
    """Aplica ``fns`` a cada columna de ``cols`` (por defecto, todas).

    * ``fns``: una función, o un diccionario ``{"nombre": función}``.
    * ``names``: plantilla con ``{col}`` y ``{fn}``. Por defecto ``"{col}"``
      con una función y ``"{col}_{fn}"`` con un diccionario.
    """
    if fns is None:
        raise TypeError("`across()` necesita `fns`.")
    return Across(everything() if cols is None else cols, fns, names)


class _IfAnyAll(Expr):
    def __init__(self, name: str, cols: Any, fn: Callable[[Expr], Any]):
        self.name, self.cols = name, cols
        self.fn = _normalize_fns(fn, name)[0][1]

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        if ctx.data is None:  # pragma: no cover - los verbos siempre pasan datos
            raise ExprError(f"`{self.name}()` necesita un contexto con datos.")
        cols = resolve(self.cols, ctx.data)
        if not cols:
            return pl.lit(self.name == "if_all")
        parts = []
        for col in cols:
            e = wrap(self.fn(Col(col))).to_polars(ctx)
            dtype = ctx.dtype(e)
            if kind(dtype) not in ("logical", "unspecified"):
                raise ExprError(f"En `{self.name}()`, la función aplicada a `{col}` debe "
                                f"devolver un vector lógico, no {type_name(dtype)}.")
            parts.append(e.cast(pl.Boolean))
        op = operator.or_ if self.name == "if_any" else operator.and_
        return reduce(op, parts)

    def columns(self) -> set[str]:
        return set()

    def __repr__(self) -> str:
        return f"{self.name}({self.cols!r}, ...)"


def if_any(cols: Any, fn: Callable[[Expr], Any]) -> _IfAnyAll:
    """TRUE si ``fn`` es TRUE para **alguna** columna seleccionada (lógica de NA de R)."""
    return _IfAnyAll("if_any", cols, fn)


def if_all(cols: Any, fn: Callable[[Expr], Any]) -> _IfAnyAll:
    """TRUE si ``fn`` es TRUE para **todas** las columnas seleccionadas."""
    return _IfAnyAll("if_all", cols, fn)


class _Pick(Expr):
    """Resultado de :func:`pick`: las columnas elegidas, como un valor único."""

    def __init__(self, cols: tuple[Any, ...]):
        self.cols = cols

    def resolve(self, data: pl.DataFrame, exclude: Sequence[str] = ()) -> list[str]:
        excluded = set(exclude)
        out: list[str] = []
        for arg in self.cols:
            for c in resolve(arg, data):
                if c not in excluded and c not in out:
                    out.append(c)
        return out

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        if ctx.data is None:  # pragma: no cover - los verbos siempre pasan datos
            raise ExprError("`pick()` necesita un contexto con datos.")
        cols = self.resolve(ctx.data, ctx.groups)
        if not cols:
            raise ExprError(
                "`pick()` debe seleccionar al menos una columna.\n"
                "ℹ Las variables de agrupación no cuentan: ya son constantes dentro del grupo."
            )
        return pl.struct([pl.col(c) for c in cols])

    def columns(self) -> set[str]:
        return set()

    def __repr__(self) -> str:
        return f"pick({', '.join(repr(wrap(c)) for c in self.cols)})"


def pick(*cols: Any) -> _Pick:
    """Las columnas seleccionadas, tratadas como un solo valor.

    Es el ``pick()`` de dplyr: no aplica ninguna función (para eso está
    :func:`across`), sino que entrega varias columnas juntas a algo que las
    necesita a la vez::

        mutate(df, orden=dense_rank(pick(f.apellido, f.nombre)))
        summarise(df, combinaciones=n_distinct(pick(f.a, f.b)))

    Como en ``across()``, las variables de agrupación quedan fuera de la
    selección: dentro de un grupo son constantes.
    """
    if not cols:
        raise TypeError("`pick()` necesita al menos una selección de columnas.")
    return _Pick(cols)
