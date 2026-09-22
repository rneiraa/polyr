"""Operaciones de conjuntos sobre filas: ``union()``, ``intersect()``, ``setdiff()``...

Tratan cada fila como un elemento, así que las dos tablas deben tener las
mismas columnas. Como en dplyr, dos filas son iguales si lo son columna a
columna y **NA cuenta como igual a NA**; todas salvo :func:`union_all`
devuelven filas únicas.
"""
from __future__ import annotations

import polars as pl

from ._core import Frame, rewrap, two_table_verb, unwrap
from ._types import cast, ptype_common
from .errors import DplyrError, ExprError

__all__ = ["union", "union_all", "intersect", "setdiff", "symdiff"]


def _align(x_in: Frame, y_in: Frame, verb_name: str
           ) -> tuple[pl.DataFrame, pl.DataFrame, list[str]]:
    """Comprueba que ambas tablas tengan las mismas columnas y unifica tipos.

    Devuelve las dos tablas con las columnas de ``x``, en el orden de ``x``.
    """
    x, groups = unwrap(x_in, verb_name, "x")
    y, _ = unwrap(y_in, verb_name, "y")
    extra = [c for c in y.columns if c not in x.columns]
    missing = [c for c in x.columns if c not in y.columns]
    if extra or missing:
        lines = ["`x` e `y` no son compatibles."]
        if extra:
            lines.append("✖ Columnas en `y` pero no en `x`: "
                         + ", ".join(f"`{c}`" for c in extra) + ".")
        if missing:
            lines.append("✖ Columnas en `x` pero no en `y`: "
                         + ", ".join(f"`{c}`" for c in missing) + ".")
        raise DplyrError(verb_name, "\n".join(lines))

    for c in x.columns:
        try:
            common = ptype_common([(f"x${c}", x.schema[c]), (f"y${c}", y.schema[c])])
            x = x.with_columns(cast(x.get_column(c), common, f"x${c}"))
            y = y.with_columns(cast(y.get_column(c), common, f"y${c}"))
        except ExprError as err:
            raise DplyrError(verb_name, str(err)) from err
    return x, y.select(x.columns), groups


def _distinct(df: pl.DataFrame) -> pl.DataFrame:
    return df.unique(keep="first", maintain_order=True)


def _by_membership(x: pl.DataFrame, y: pl.DataFrame, how: str) -> pl.DataFrame:
    if not x.columns:  # sin columnas no hay nada que comparar
        return x.head(0)
    return _distinct(x).join(y, on=x.columns, how=how, nulls_equal=True, maintain_order="left")


@two_table_verb
def union(x: Frame, y: Frame, /) -> Frame:
    """Filas únicas que están en ``x`` o en ``y``, en orden de aparición."""
    xd, yd, groups = _align(x, y, "union")
    return rewrap(_distinct(pl.concat([xd, yd])), groups)


@two_table_verb
def union_all(x: Frame, y: Frame, /) -> Frame:
    """Todas las filas de ``x`` seguidas de todas las de ``y``, sin quitar repetidas.

    Se diferencia de ``bind_rows()`` en que exige las mismas columnas en
    ambas tablas.
    """
    xd, yd, groups = _align(x, y, "union_all")
    return rewrap(pl.concat([xd, yd]), groups)


@two_table_verb
def intersect(x: Frame, y: Frame, /) -> Frame:
    """Filas únicas de ``x`` que también están en ``y``, en el orden de ``x``."""
    xd, yd, groups = _align(x, y, "intersect")
    return rewrap(_by_membership(xd, yd, "semi"), groups)


@two_table_verb
def setdiff(x: Frame, y: Frame, /) -> Frame:
    """Filas únicas de ``x`` que **no** están en ``y``, en el orden de ``x``."""
    xd, yd, groups = _align(x, y, "setdiff")
    return rewrap(_by_membership(xd, yd, "anti"), groups)


@two_table_verb
def symdiff(x: Frame, y: Frame, /) -> Frame:
    """Filas únicas que están en una sola de las dos tablas (primero las de ``x``)."""
    xd, yd, groups = _align(x, y, "symdiff")
    solo_x = _by_membership(xd, yd, "anti")
    solo_y = _by_membership(yd, xd, "anti")
    return rewrap(pl.concat([solo_x, solo_y]), groups)
