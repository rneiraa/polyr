"""Selección de filas por posición: la familia ``slice_*()``.

``slice()`` con posiciones numéricas no se implementa a propósito: dplyr usa
posiciones base 1 y Python base 0, y cualquiera de las dos elecciones
provocaría errores silenciosos (ver ``docs/diferencias-con-dplyr.md``).
"""
from __future__ import annotations

from typing import Any

import polars as pl

from ._core import Frame, evaluate, recycle, resolve_by, rewrap, sort_by_groups, unwrap, verb
from .errors import DplyrError
from .expr import wrap

__all__ = ["slice_head", "slice_tail", "slice_min", "slice_max", "slice_sample"]

_POS, _KEY = "__polyr_pos__", "__polyr_key__"


def _size_expr(n: Any, prop: Any, verb_name: str) -> pl.Expr:
    """Tamaño por grupo. Negativo significa "todas menos"."""
    if n is not None and prop is not None:
        raise DplyrError(verb_name, "Usa `n` o `prop`, no ambos.")
    if prop is not None:
        if not isinstance(prop, (int, float)) or isinstance(prop, bool):
            raise DplyrError(verb_name, "`prop` debe ser un número.")
        size = (pl.len().cast(pl.Float64) * abs(prop)).floor().cast(pl.Int64)
        negative = prop < 0
    else:
        n = 1 if n is None else n
        if not isinstance(n, int) or isinstance(n, bool):
            raise DplyrError(verb_name, "`n` debe ser un número entero.")
        size = pl.lit(abs(n), dtype=pl.Int64)
        negative = n < 0
    size = pl.min_horizontal(size, pl.len().cast(pl.Int64))
    return pl.len().cast(pl.Int64) - size if negative else size


def _window(e: pl.Expr, keys: list[str]) -> pl.Expr:
    return e.over(keys) if keys else e


def _finish(df: pl.DataFrame, keep: pl.Expr, keys: list[str]) -> pl.DataFrame:
    out = df.filter(keep)
    return out.drop([c for c in (_POS, _KEY) if c in out.columns])


@verb
def slice_head(data: Frame, /, n: int | None = None, prop: float | None = None,
               _by: Any = None) -> Frame:
    """Primeras ``n`` filas (o proporción ``prop``) de cada grupo."""
    df, groups = unwrap(data, "slice_head")
    keys, _ = resolve_by(df, groups, _by, "slice_head")
    size = _size_expr(n, prop, "slice_head")
    df = sort_by_groups(df, keys)
    keep = _window(pl.int_range(pl.len()) < size, keys)
    return rewrap(_finish(df, keep, keys), groups)


@verb
def slice_tail(data: Frame, /, n: int | None = None, prop: float | None = None,
               _by: Any = None) -> Frame:
    """Últimas ``n`` filas (o proporción ``prop``) de cada grupo."""
    df, groups = unwrap(data, "slice_tail")
    keys, _ = resolve_by(df, groups, _by, "slice_tail")
    size = _size_expr(n, prop, "slice_tail")
    df = sort_by_groups(df, keys)
    keep = _window(pl.int_range(pl.len()) >= pl.len() - size, keys)
    return rewrap(_finish(df, keep, keys), groups)


def _slice_extreme(verb_name: str, data: Frame, order_by: Any, n: Any, prop: Any,
                   with_ties: bool, na_rm: bool, _by: Any, descending: bool) -> Frame:
    df, groups = unwrap(data, verb_name)
    keys, _ = resolve_by(df, groups, _by, verb_name)
    size = _size_expr(n, prop, verb_name)
    expr = wrap(order_by)
    key = evaluate(df, expr, verb_name, repr(expr), keys)
    key = recycle(key, df.height, verb_name, repr(expr), "`order_by`")
    if key.dtype.is_float():
        key = key.fill_nan(None)
    df = df.with_columns(key.alias(_KEY))
    df = df.sort(keys + [_KEY], descending=[False] * len(keys) + [descending],
                 nulls_last=True, maintain_order=True)
    k = pl.col(_KEY)
    pos = _window(pl.int_range(pl.len()), keys)
    if with_ties:
        rank = _window(k.rank("min", descending=descending), keys)
        keep_value = k.is_not_null() & (rank <= _window(size, keys))
    else:
        keep_value = k.is_not_null() & (pos < _window(size, keys))
    keep = keep_value
    if not na_rm:  # los NA completan el tamaño pedido, al final
        keep = keep | (k.is_null() & (pos < _window(size, keys)))
    return rewrap(_finish(df, keep, keys), groups)


@verb
def slice_min(data: Frame, /, order_by: Any, n: int | None = None, prop: float | None = None,
              with_ties: bool = True, na_rm: bool = False, _by: Any = None) -> Frame:
    """Filas con los menores valores de ``order_by`` en cada grupo.

    Como en dplyr, ``with_ties=True`` (defecto) incluye los empates, por lo
    que puede devolver más de ``n`` filas; los NA se usan solo para completar.
    """
    return _slice_extreme("slice_min", data, order_by, n, prop, with_ties, na_rm, _by, False)


@verb
def slice_max(data: Frame, /, order_by: Any, n: int | None = None, prop: float | None = None,
              with_ties: bool = True, na_rm: bool = False, _by: Any = None) -> Frame:
    """Filas con los mayores valores de ``order_by`` en cada grupo."""
    return _slice_extreme("slice_max", data, order_by, n, prop, with_ties, na_rm, _by, True)


@verb
def slice_sample(data: Frame, /, n: int | None = None, prop: float | None = None,
                 replace: bool = False, weight_by: Any = None, seed: int | None = None,
                 _by: Any = None) -> Frame:
    """Muestra aleatoria de filas por grupo. ``seed`` la hace reproducible.

    El generador aleatorio no es el de R: con la misma semilla no se obtienen
    las mismas filas que en dplyr.
    """
    df, groups = unwrap(data, "slice_sample")
    keys, _ = resolve_by(df, groups, _by, "slice_sample")
    if replace or weight_by is not None:
        raise DplyrError("slice_sample", "`replace` y `weight_by` todavía no están "
                                         "implementados (ver ROADMAP.md).")
    size = _size_expr(n, prop, "slice_sample")
    df = sort_by_groups(df, keys)
    order = _window(pl.int_range(pl.len()).shuffle(seed=seed), keys)
    return rewrap(_finish(df, order < _window(size, keys), keys), groups)
