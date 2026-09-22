"""Infraestructura común de los verbos: pipe, data mask y manejo de errores."""
from __future__ import annotations

import functools
from typing import Any, Callable, Sequence

import polars as pl

from . import _types
from .errors import DplyrError, ExprError
from .expr import EvalContext, Expr, wrap
from .grouped import GroupedFrame
from .tidyselect import eval_select, resolve

Frame = pl.DataFrame | GroupedFrame


# --- pipe ---------------------------------------------------------------------

class Pipeable:
    """Verbo con argumentos pero sin datos, a la espera de ``datos >> verbo``."""

    def __init__(self, fn: Callable, args: tuple, kwargs: dict):
        self._fn, self._args, self._kwargs = fn, args, kwargs

    def __rrshift__(self, data: Any) -> Any:
        return self._fn(data, *self._args, **self._kwargs)

    def __repr__(self) -> str:
        return f"<verbo {self._fn.__name__}() esperando datos: usa df >> ...>"


def verb(fn: Callable) -> Callable:
    """Decorador: el verbo funciona con llamada directa y con ``>>``."""
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if args and isinstance(args[0], (pl.DataFrame, GroupedFrame)):
            return fn(*args, **kwargs)
        if args and _looks_like_data(args[0]):
            fn(*args, **kwargs)  # deja que unwrap() dé un error claro
        return Pipeable(fn, args, kwargs)
    return wrapper


def _looks_like_data(obj: Any) -> bool:
    return isinstance(obj, pl.LazyFrame) or type(obj).__name__ == "DataFrame"


def two_table_verb(fn: Callable) -> Callable:
    """Como :func:`verb`, para verbos de dos tablas (``x >> left_join(y)``)."""
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        frames = [a for a in args[:2] if isinstance(a, (pl.DataFrame, GroupedFrame))]
        if len(frames) >= 2:
            return fn(*args, **kwargs)
        return Pipeable(fn, args, kwargs)
    return wrapper


# --- datos y grupos -----------------------------------------------------------

def unwrap(data: Any, verb_name: str, arg: str = "data") -> tuple[pl.DataFrame, list[str]]:
    if isinstance(data, GroupedFrame):
        return data.data, data.groups
    if isinstance(data, pl.DataFrame):
        return data, []
    if isinstance(data, pl.LazyFrame):
        raise DplyrError(verb_name, f"`{arg}` es un LazyFrame; usa `.collect()` primero "
                                    "(el soporte perezoso está en el ROADMAP).")
    hint = "\nℹ Convierte un DataFrame de pandas con `pl.from_pandas(df)`." \
        if type(data).__name__ == "DataFrame" else ""
    raise DplyrError(verb_name, f"`{arg}` debe ser un DataFrame de polars, no "
                                f"`{type(data).__name__}`.{hint}")


def rewrap(df: pl.DataFrame, groups: Sequence[str]) -> Frame:
    groups = [g for g in groups if g in df.columns]
    return GroupedFrame(df, groups) if groups else df


def resolve_by(df: pl.DataFrame, groups: list[str], by: Any, verb_name: str
               ) -> tuple[list[str], bool]:
    """Grupos efectivos de una operación. Devuelve ``(grupos, vienen_de_by)``."""
    if by is None:
        return groups, False
    if groups:
        raise DplyrError(verb_name, "No se puede usar `_by` con un data frame agrupado.\n"
                                    "ℹ Usa `ungroup()` primero o no uses `_by`.")
    return resolve_cols(by, df, verb_name, "_by"), True


# --- evaluación ---------------------------------------------------------------

def check_columns(expr: Expr, available: Sequence[str], verb_name: str, argument: str) -> None:
    missing = sorted(expr.columns() - set(available))
    if missing:
        raise DplyrError(verb_name, f"No se encontró la columna `{missing[0]}`.", argument)


def compile_expr(df: pl.DataFrame, expr: Expr, verb_name: str, argument: str) -> pl.Expr:
    check_columns(expr, df.columns, verb_name, argument)
    try:
        return expr.to_polars(EvalContext(df.schema, df))
    except ExprError as err:
        raise DplyrError(verb_name, str(err), argument) from err
    except pl.exceptions.PolarsError as err:
        raise DplyrError(verb_name, polars_message(err), argument) from err


def dtype_of(df: pl.DataFrame, compiled: pl.Expr) -> pl.DataType:
    return EvalContext(df.schema).dtype(compiled)


def evaluate(df: pl.DataFrame, expr: Expr, verb_name: str, argument: str,
             groups: Sequence[str] = ()) -> pl.Series:
    """Evalúa ``expr`` en la data mask. Con grupos, se evalúa en cada grupo
    y el resultado vuelve a tener una fila por fila de ``df``."""
    compiled = compile_expr(df, expr, verb_name, argument)
    if groups:
        compiled = compiled.over(list(groups))
    try:
        return df.select(compiled.alias("__value__")).to_series()
    except pl.exceptions.ShapeError as err:
        raise DplyrError(
            verb_name,
            "El resultado debe tener el tamaño del grupo o tamaño 1.",
            argument,
        ) from err
    except pl.exceptions.PolarsError as err:
        raise DplyrError(verb_name, polars_message(err), argument) from err


def polars_message(err: Exception) -> str:
    return str(err).strip().splitlines()[0]


def recycle(s: pl.Series, n: int, verb_name: str, argument: str, what: str) -> pl.Series:
    try:
        return _types.recycle(s, n, what)
    except ExprError as err:
        raise DplyrError(verb_name, str(err), argument) from err


# --- selección ----------------------------------------------------------------

def select_cols(df: pl.DataFrame, args: Sequence[Any], named: dict[str, Any],
                verb_name: str) -> dict[str, str]:
    try:
        return eval_select(df, args, named)
    except ExprError as err:
        raise DplyrError(verb_name, str(err)) from err


def resolve_cols(node: Any, df: pl.DataFrame, verb_name: str, argument: str) -> list[str]:
    try:
        return resolve(node, df)
    except ExprError as err:
        raise DplyrError(verb_name, str(err), argument) from err


def relocate_order(columns: Sequence[str], moved: Sequence[str],
                   before: Sequence[str] | None, after: Sequence[str] | None) -> list[str]:
    """Nuevo orden de columnas moviendo ``moved`` antes/después de un ancla."""
    moved_set = set(moved)
    remaining = [c for c in columns if c not in moved_set]
    if before is not None:
        anchors = [remaining.index(c) for c in before if c in remaining]
        pos = min(anchors) if anchors else 0
    elif after is not None:
        anchors = [remaining.index(c) for c in after if c in remaining]
        pos = max(anchors) + 1 if anchors else len(remaining)
    else:
        pos = 0
    return remaining[:pos] + list(moved) + remaining[pos:]


def anchors(df: pl.DataFrame, before: Any, after: Any, verb_name: str
            ) -> tuple[list[str] | None, list[str] | None]:
    if before is not None and after is not None:
        raise DplyrError(verb_name, "Solo puedes usar `_before` o `_after`, no ambos.")
    b = None if before is None else resolve_cols(before, df, verb_name, "_before")
    a = None if after is None else resolve_cols(after, df, verb_name, "_after")
    return b, a


def reject_named(verb_name: str, named: dict[str, Any], hint: str = "") -> None:
    if named:
        name = next(iter(named))
        raise DplyrError(verb_name, f"Argumento con nombre inesperado: `{name}=`.{hint}")


def not_yet(verb_name: str, arg: str, value: Any, default: Any = None) -> None:
    if value is not default and value != default:
        raise DplyrError(verb_name, f"`{arg}` todavía no está implementado (ver ROADMAP.md).")


def sort_by_groups(df: pl.DataFrame, groups: Sequence[str]) -> pl.DataFrame:
    """Orden estable por grupos, como el orden de grupos de dplyr."""
    if not groups:
        return df
    return df.sort(list(groups), nulls_last=True, maintain_order=True)


def as_expr(value: Any) -> Expr:
    return wrap(value)
