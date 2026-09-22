"""Resúmenes: ``summarise()``, ``count()``, ``tally()``, ``add_count()``."""
from __future__ import annotations

import copy
import inspect
from typing import Any

import polars as pl

from ._core import (Frame, compile_expr, dtype_of, polars_message, resolve_by, rewrap,
                    sort_by_groups, unwrap, verb)
from .across import Across
from .errors import DplyrError, inform
from .expr import wrap
from .functions import n as n_fn
from .functions import sum as sum_fn
from .expr import Col
from .functions import desc
from .verbs import _across_items, _expand_items, _key_columns, arrange, mutate

__all__ = ["summarise", "summarize", "reframe", "count", "tally", "add_count"]

_GROUPS = ("drop_last", "drop", "keep")


def _size_error(name: str, size: int, group: str = "") -> DplyrError:
    where = f" en el grupo {group}" if group else ""
    return DplyrError(
        "summarise",
        f"`{name}` debe tener tamaño 1, no {size}{where}.\n"
        "ℹ `summarise()` produce una fila por grupo; para resultados de otro tamaño "
        "usa `reframe()`.",
        name,
    )


class _Summary(Col):
    """Referencia a un resumen ya calculado: dentro de summarise vale un único
    valor por grupo (como en dplyr), no una columna repetida."""

    def to_polars(self, ctx):  # type: ignore[override]
        return pl.col(self.name).first()


def _scalarize(expr: Any, names: set[str]) -> Any:
    """Reemplaza las referencias a resúmenes previos por :class:`_Summary`."""
    if not names:
        return expr
    if isinstance(expr, Col) and not isinstance(expr, _Summary):
        return _Summary(expr.name) if expr.name in names else expr
    clone = copy.copy(expr)
    for attr in ("left", "right", "operand", "inner"):
        if hasattr(clone, attr):
            setattr(clone, attr, _scalarize(getattr(clone, attr), names))
    if hasattr(clone, "args") and isinstance(clone.args, list):
        clone.args = [_scalarize(a, names) for a in clone.args]
    return clone


def summarise_frame(df: pl.DataFrame, keys: list[str], items: list[tuple[str, Any]]
                    ) -> pl.DataFrame:
    """Núcleo de summarise: devuelve un DataFrame sin grupos, una fila por grupo."""
    working = df
    results: list[str] = []
    ungrouped_values: dict[str, pl.Series] = {}
    queue = list(items)
    while queue:
        name, value = queue.pop(0)
        if isinstance(value, Across):
            queue = _across_items(working, value, keys, "summarise") + queue
            continue
        if name in keys:
            raise DplyrError("summarise", f"No se puede modificar la variable de agrupación `{name}`.")
        if value is None:
            results = [r for r in results if r != name]
            ungrouped_values.pop(name, None)
            continue
        expr = wrap(value)
        label = f"{name} = {expr!r}"
        compiled = compile_expr(working, _scalarize(expr, set(results)), "summarise", label)

        if not keys:
            try:
                s = working.select(compiled.alias(name)).to_series()
            except pl.exceptions.PolarsError as err:
                raise DplyrError("summarise", polars_message(err), label) from err
            if len(s) != 1:
                raise _size_error(name, len(s))
            ungrouped_values[name] = s
            working = working.with_columns(s.new_from_index(0, working.height))
        else:
            try:
                agg = working.group_by(keys, maintain_order=True).agg(compiled.alias(name))
            except pl.exceptions.PolarsError as err:
                raise DplyrError("summarise", polars_message(err), label) from err
            row_dtype = dtype_of(working, compiled)
            if agg.schema[name] == pl.List(row_dtype) and row_dtype != agg.schema[name]:
                lengths = agg[name].list.len()
                bad = (lengths != 1).arg_true()
                if len(bad):
                    i = bad[0]
                    key = ", ".join(f"{k} = {agg[k][i]!r}" for k in keys)
                    raise _size_error(name, lengths[i], key)
                agg = agg.with_columns(pl.col(name).list.first())
            working = working.drop(name, strict=False).join(
                agg, on=keys, how="left", nulls_equal=True, maintain_order="left")
        results = [r for r in results if r != name] + [name]

    if not keys:
        return pl.DataFrame([ungrouped_values[r] for r in results])
    out = working.group_by(keys, maintain_order=True).agg([pl.col(r).first() for r in results])
    return sort_by_groups(out, keys)


@verb
def summarise(data: Frame, /, *args: Any, _by: Any = None, _groups: str | None = None,
              **named: Any) -> Frame:
    """Resume cada grupo a una fila.

    * Se evalúa en orden: cada resumen puede usar los anteriores.
    * Cada resultado debe tener tamaño 1 por grupo.
    * El resultado queda ordenado por las variables de agrupación.
    * ``_groups``: ``"drop_last"`` (defecto con grupos), ``"drop"`` o ``"keep"``.
      Con más de una variable de agrupación y sin ``_groups`` se informa el
      agrupamiento resultante, como en dplyr.
    """
    df, groups = unwrap(data, "summarise")
    keys, from_by = resolve_by(df, groups, _by, "summarise")
    if _groups is not None and _groups not in _GROUPS:
        raise DplyrError("summarise", f"`_groups` debe ser uno de {', '.join(map(repr, _GROUPS))}, "
                                      f"no {_groups!r}.")
    items = _expand_items(df, args, named, keys, "summarise")
    out = summarise_frame(df, keys, items)

    if from_by or not keys:
        return out
    mode = _groups
    if mode is None:
        mode = "drop_last"
        if len(keys) > 1:
            inform(f"`summarise()` agrupó el resultado por {', '.join(map(repr, keys[:-1]))}. "
                   "Puedes cambiarlo con el argumento `_groups`.")
    remaining = {"drop_last": keys[:-1], "drop": [], "keep": keys}[mode]
    return rewrap(out, remaining)


summarize = summarise


def _count_name(name: str | None, existing: list[str]) -> str:
    if name is not None:
        return name
    name = "n"
    while name in existing:
        name = "n" + name
    if name != "n":
        inform(f"Guardando el conteo en `{name}`: `n` ya existe en los datos.\n"
               "ℹ Usa `name=` para elegir otro nombre.")
    return name


def _wt_item(wt: Any, name: str) -> tuple[str, Any]:
    return (name, n_fn() if wt is None else sum_fn(wt, na_rm=True))


@verb
def count(data: Frame, /, *args: Any, wt: Any = None, sort: bool = False,
          name: str | None = None, **named: Any) -> Frame:
    """Cuenta filas por combinación de valores: ``count(df, f.a, f.b)``.

    Equivale a ``group_by(...) >> summarise(n=n())`` (o ``sum(wt)`` con
    ``wt``). El resultado conserva los grupos originales de ``data``.
    """
    df, groups = unwrap(data, "count")
    df, cols = _key_columns(df, groups, args, named, "count")
    keys = list(dict.fromkeys(groups + cols))
    col_name = _count_name(name, keys)
    out = summarise_frame(df, keys, [_wt_item(wt, col_name)])
    if sort:
        out = arrange(out, desc(pl_col(col_name)))
    return rewrap(out, groups)


def pl_col(name: str) -> Col:
    return Col(name)


@verb
def tally(data: Frame, /, wt: Any = None, sort: bool = False, name: str | None = None) -> Frame:
    """Cuenta filas por grupo (``count()`` sin columnas adicionales).

    Como en dplyr, el resultado pierde el último nivel de agrupación.
    """
    df, groups = unwrap(data, "tally")
    col_name = _count_name(name, groups)
    out = summarise_frame(df, groups, [_wt_item(wt, col_name)])
    if sort:
        out = arrange(out, desc(pl_col(col_name)))
    return rewrap(out, groups[:-1])


@verb
def add_count(data: Frame, /, *args: Any, wt: Any = None, sort: bool = False,
              name: str | None = None, **named: Any) -> Frame:
    """Como ``count()``, pero agrega el conteo como columna sin resumir filas."""
    df, groups = unwrap(data, "add_count")
    df, cols = _key_columns(df, groups, args, named, "add_count")
    keys = list(dict.fromkeys(groups + cols))
    col_name = _count_name(name, df.columns)
    item = _wt_item(wt, col_name)
    out = mutate(df, **{item[0]: item[1]}, _by=keys) if keys else mutate(df, **{item[0]: item[1]})
    if sort:
        out = arrange(out, desc(pl_col(col_name)))
    return rewrap(out, groups)


_DUMMY = "__polyr_reframe_group__"
_EXPLODE_HAS_EMPTY = "empty_as_null" in inspect.signature(pl.DataFrame.explode).parameters


def _explode(df: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
    """Un grupo que produce 0 filas no aporta filas (como en dplyr)."""
    if _EXPLODE_HAS_EMPTY:
        return df.explode(cols, empty_as_null=False)
    return df.filter(pl.col(cols[0]).list.len() > 0).explode(cols)


@verb
def reframe(data: Frame, /, *args: Any, _by: Any = None, **named: Any) -> pl.DataFrame:
    """Como ``summarise()``, pero cada grupo puede producir cualquier número de filas.

    * Dentro de un grupo, todos los resultados deben tener el mismo tamaño
      (o tamaño 1, que se recicla), igual que en dplyr.
    * El resultado siempre queda **sin grupos**, ordenado por las variables
      de agrupación.
    * A diferencia de ``summarise()``, un resultado no puede usar otro creado
      en la misma llamada (todavía; ver ROADMAP.md).
    """
    df, groups = unwrap(data, "reframe")
    keys, _ = resolve_by(df, groups, _by, "reframe")
    raw = _expand_items(df, args, named, keys, "reframe")
    items: list[tuple[str, Any]] = []
    for name, value in raw:
        items += _across_items(df, value, keys, "reframe") if isinstance(value, Across) \
            else [(name, value)]

    created: set[str] = set()
    compiled: list[tuple[str, pl.Expr, pl.DataType]] = []
    for name, value in items:
        if name in keys:
            raise DplyrError("reframe", f"No se puede modificar la variable de agrupación `{name}`.")
        if value is None:
            compiled = [c for c in compiled if c[0] != name]
            continue
        expr = wrap(value)
        label = f"{name} = {expr!r}"
        if expr.columns() & created:
            raise DplyrError("reframe", "Usar un resultado creado en la misma llamada a "
                                        "`reframe()` todavía no está implementado.", label)
        c = compile_expr(df, expr, "reframe", label)
        compiled = [x for x in compiled if x[0] != name] + [(name, c.alias(name), dtype_of(df, c))]
        created.add(name)

    group_cols = keys or [_DUMMY]
    work = df if keys else df.with_columns(pl.lit(0).alias(_DUMMY))
    try:
        agg = work.group_by(group_cols, maintain_order=True).agg([c for _, c, _ in compiled])
    except pl.exceptions.PolarsError as err:
        raise DplyrError("reframe", polars_message(err)) from err

    list_cols = [n for n, _, dt in compiled if agg.schema[n] == pl.List(dt) and dt != agg.schema[n]]
    if list_cols:
        lens = [pl.col(n).list.len() for n in list_cols]
        agg = agg.with_columns(pl.max_horizontal(lens).alias("__target__"))
        for n in list_cols:
            ln = pl.col(n).list.len()
            bad = agg.filter((ln != 1) & (ln != pl.col("__target__")))
            if not bad.is_empty():
                raise DplyrError(
                    "reframe",
                    f"`{n}` debe tener el tamaño de los demás resultados del grupo "
                    f"({bad['__target__'][0]}) o 1, no {bad.select(ln)[n][0]}.",
                    n,
                )
        agg = agg.with_columns([
            pl.when(pl.col(n).list.len() == pl.col("__target__")).then(pl.col(n))
            .otherwise(pl.col(n).list.first().repeat_by(pl.col("__target__"))).alias(n)
            for n in list_cols
        ]).drop("__target__")
        agg = _explode(agg, list_cols)
    out = sort_by_groups(agg, keys) if keys else agg.drop(_DUMMY)
    return out
