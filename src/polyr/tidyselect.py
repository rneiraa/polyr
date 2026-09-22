"""Lenguaje de selección de columnas: el equivalente de tidyselect.

Una selección se escribe con los mismos nodos que cualquier expresión, pero
se interpreta de otra forma: en lugar de calcular valores, se resuelve a una
lista **ordenada** de nombres de columnas.

=====================  ==========================  ===========================
R (tidyselect)         polyr                          Significado
=====================  ==========================  ===========================
``x``, ``"x"``         ``f.x``, ``"x"``             una columna
``a:c``                ``f["a":"c"]``               rango (inclusive)
``-x``                 ``-f.x``                     excluir de lo seleccionado
``!x``                 ``~f.x``                     complemento
``a | b``, ``a & b``   ``a | b``, ``a & b``         unión, intersección
``c(a, b)``            ``["a", "b"]``               vector de nombres
=====================  ==========================  ===========================

Reglas (las mismas de tidyselect):

* El orden del resultado es el orden de aparición.
* Si el **primer** argumento es una exclusión (``-f.x``), se parte de todas
  las columnas.
* Los helpers de texto ignoran mayúsculas por defecto (``ignore_case=True``),
  igual que en R.
* Pedir una columna inexistente es un error, salvo con :func:`any_of`.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Sequence

import polars as pl

from .errors import ExprError
from .expr import BinOp, Col, EvalContext, Expr, Lit, UnaryOp, Values, wrap

__all__ = [
    "starts_with", "ends_with", "contains", "matches", "num_range",
    "everything", "last_col", "all_of", "any_of", "where", "col_range",
]


class Selector(Expr):
    """Helper de selección (``starts_with()``, ``where()``...)."""

    def __init__(self, label: str, resolver: Callable[[pl.DataFrame], list[str]]):
        self._label, self._resolver = label, resolver

    def resolve(self, data: pl.DataFrame) -> list[str]:
        return self._resolver(data)

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        raise ExprError(
            f"`{self._label}` es un selector de columnas: solo puede usarse en "
            "`select()`, `rename()`, `relocate()` o `pull()`."
        )

    def columns(self) -> set[str]:
        return set()

    def __repr__(self) -> str:
        return self._label


# --- resolución ---------------------------------------------------------------

def _missing_error(names: Sequence[str]) -> ExprError:
    shown = ", ".join(f"`{n}`" for n in names)
    what = "La columna" if len(names) == 1 else "Las columnas"
    verb = "no existe" if len(names) == 1 else "no existen"
    return ExprError(f"No se pueden seleccionar columnas que no existen.\n✖ {what} {shown} {verb}.")


def _union(a: list[str], b: list[str]) -> list[str]:
    seen = set(a)
    return a + [c for c in b if c not in seen]


def resolve(node: Any, data: pl.DataFrame) -> list[str]:
    """Resuelve un nodo de selección a una lista ordenada de columnas."""
    node = wrap(node)
    cols = data.columns
    if isinstance(node, Selector):
        return node.resolve(data)
    if isinstance(node, Col) or (isinstance(node, Lit) and isinstance(node.value, str)):
        name = node.name if isinstance(node, Col) else node.value
        if name not in cols:
            raise _missing_error([name])
        return [name]
    if isinstance(node, Values):
        return all_of(node.values.to_list()).resolve(data)
    if isinstance(node, UnaryOp) and node.op in ("-", "~"):
        excluded = set(resolve(node.operand, data))
        return [c for c in cols if c not in excluded]
    if isinstance(node, BinOp) and node.op == "|":
        return _union(resolve(node.left, data), resolve(node.right, data))
    if isinstance(node, BinOp) and node.op == "&":
        right = set(resolve(node.right, data))
        return [c for c in resolve(node.left, data) if c in right]
    raise ExprError(
        f"`{node!r}` no es una selección de columnas válida.\n"
        "ℹ Aquí solo se aceptan nombres de columnas (f.x, \"x\") y selectores "
        "como starts_with() o where()."
    )


def eval_select(data: pl.DataFrame, args: Sequence[Any], named: dict[str, Any],
                ) -> dict[str, str]:
    """Evalúa una selección completa. Devuelve ``{nombre_original: nombre_nuevo}``
    en el orden resultante."""
    selected: dict[str, str] = {}
    for i, arg in enumerate(args):
        node = wrap(arg)
        if isinstance(node, UnaryOp) and node.op == "-":
            if i == 0:
                selected = {c: c for c in data.columns}
            for c in resolve(node.operand, data):
                selected.pop(c, None)
        else:
            for c in resolve(node, data):
                selected.setdefault(c, c)
    for new, arg in named.items():
        found = resolve(arg, data)
        if len(found) != 1:
            raise ExprError(
                f"El renombre `{new}` debe seleccionar exactamente una columna, "
                f"pero seleccionó {len(found)}."
            )
        selected[found[0]] = new
    check_unique(list(selected.values()))
    return selected


def check_unique(names: Iterable[str]) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ExprError(
                f"Los nombres de las columnas deben ser únicos.\n✖ El nombre `{name}` está repetido."
            )
        seen.add(name)


# --- helpers ------------------------------------------------------------------

def _text_selector(fname: str, test: Callable[[str, str], bool],
                   match: tuple[str, ...], ignore_case: bool) -> Selector:
    if not match or not all(isinstance(m, str) for m in match):
        raise TypeError(f"`{fname}()` necesita uno o más strings.")

    def resolver(data: pl.DataFrame) -> list[str]:
        norm = str.casefold if ignore_case else (lambda s: s)
        return [c for c in data.columns if any(test(norm(c), norm(m)) for m in match)]

    label = f"{fname}({', '.join(map(repr, match))}" + ("" if ignore_case else ", ignore_case=False") + ")"
    return Selector(label, resolver)


def starts_with(*match: str, ignore_case: bool = True) -> Selector:
    """Columnas cuyo nombre empieza con alguno de los prefijos."""
    return _text_selector("starts_with", str.startswith, match, ignore_case)


def ends_with(*match: str, ignore_case: bool = True) -> Selector:
    """Columnas cuyo nombre termina con alguno de los sufijos."""
    return _text_selector("ends_with", str.endswith, match, ignore_case)


def contains(*match: str, ignore_case: bool = True) -> Selector:
    """Columnas cuyo nombre contiene alguno de los textos (literales)."""
    return _text_selector("contains", lambda c, m: m in c, match, ignore_case)


def matches(pattern: str, ignore_case: bool = True) -> Selector:
    """Columnas cuyo nombre coincide con la expresión regular."""
    regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    return Selector(f"matches({pattern!r})",
                    lambda data: [c for c in data.columns if regex.search(c)])


def num_range(prefix: str, range: Iterable[int], suffix: str = "",
              width: int | None = None) -> Selector:
    """Columnas como ``x1, x2, x3`` (``width`` rellena con ceros: ``x01``)."""
    nums = list(range)
    names = [f"{prefix}{str(i).zfill(width) if width else i}{suffix}" for i in nums]
    return Selector(f"num_range({prefix!r}, ...)",
                    lambda data: [n for n in names if n in data.columns])


def everything() -> Selector:
    """Todas las columnas."""
    return Selector("everything()", lambda data: list(data.columns))


def last_col(offset: int = 0) -> Selector:
    """La última columna (``offset=1`` es la penúltima, etc.)."""
    def resolver(data: pl.DataFrame) -> list[str]:
        if not 0 <= offset < data.width:
            raise ExprError(f"`offset` ({offset}) debe ser menor que el número de columnas ({data.width}).")
        return [data.columns[-1 - offset]]
    return Selector("last_col()" if offset == 0 else f"last_col({offset})", resolver)


def all_of(names: Iterable[str]) -> Selector:
    """Columnas nombradas en un vector; **todas** deben existir."""
    names = list(names)

    def resolver(data: pl.DataFrame) -> list[str]:
        missing = [n for n in names if n not in data.columns]
        if missing:
            raise _missing_error(missing)
        return list(dict.fromkeys(names))
    return Selector("all_of(...)", resolver)


def any_of(names: Iterable[str]) -> Selector:
    """Columnas nombradas en un vector; las que no existen se ignoran."""
    names = list(names)
    return Selector("any_of(...)",
                    lambda data: list(dict.fromkeys(n for n in names if n in data.columns)))


def where(predicate: Callable[[pl.Series], bool]) -> Selector:
    """Columnas para las que ``predicate(serie)`` es ``True``.

    Ejemplo: ``where(is_numeric)``.
    """
    if not callable(predicate):
        raise TypeError("`where()` necesita una función.")

    def resolver(data: pl.DataFrame) -> list[str]:
        out = []
        for c in data.columns:
            result = predicate(data.get_column(c))
            if not isinstance(result, bool):
                raise ExprError(
                    f"El predicado de `where()` debe devolver True o False, "
                    f"no `{type(result).__name__}` (columna `{c}`)."
                )
            if result:
                out.append(c)
        return out
    name = getattr(predicate, "__name__", "<función>")
    return Selector(f"where({name})", resolver)


def col_range(start: str | None, stop: str | None) -> Selector:
    """Rango inclusivo de columnas por posición, como ``a:c`` en R.

    ``f["a":]`` va hasta la última; ``f[:"c"]`` desde la primera. Si ``stop``
    está antes que ``start``, el orden se invierte (como en R).
    """
    def resolver(data: pl.DataFrame) -> list[str]:
        cols = data.columns
        for name in (start, stop):
            if name is not None and name not in cols:
                raise _missing_error([name])
        i = 0 if start is None else cols.index(start)
        j = len(cols) - 1 if stop is None else cols.index(stop)
        return cols[i:j + 1] if i <= j else cols[j:i + 1][::-1]
    label = f"f[{start!r}:{stop!r}]".replace("None", "")
    return Selector(label, resolver)
