"""Combinar tablas por filas o columnas: ``bind_rows()``, ``bind_cols()``."""
from __future__ import annotations

from typing import Any, Mapping

import polars as pl

from ._core import Frame, rewrap, unwrap
from ._types import cast, ptype_common
from .errors import DplyrError, ExprError, inform

__all__ = ["bind_rows", "bind_cols"]


def bind_rows(*frames: Any, _id: str | None = None) -> Frame:
    """Apila tablas por filas, emparejando columnas por nombre.

    * Las columnas que faltan en una tabla se llenan con NA.
    * Cada columna se lleva al tipo común de todas las tablas (reglas de
      vctrs): ``<integer>`` con ``<double>`` da ``<double>``;
      ``<character>`` con ``<double>`` es un error.
    * Acepta tablas sueltas, una lista o un diccionario ``{id: tabla}``.
    * ``_id`` agrega una columna identificando el origen de cada fila (las
      claves del diccionario, o "1", "2", ... como en dplyr).
    * El resultado conserva los grupos de la primera tabla.
    """
    items: list[tuple[str, Any]] = []
    for arg in frames:
        if isinstance(arg, Mapping):
            items += [(str(k), v) for k, v in arg.items()]
        elif isinstance(arg, (list, tuple)):
            items += [("", v) for v in arg]
        elif arg is not None:
            items.append(("", arg))
    items = [(k or str(i), v) for i, (k, v) in enumerate(items, 1)]
    if not items:
        return pl.DataFrame()

    unwrapped = [(key, *unwrap(frame, "bind_rows", f"..{i}"))
                 for i, (key, frame) in enumerate(items, 1)]
    groups = unwrapped[0][2]
    columns: list[str] = []
    for _, df, _ in unwrapped:
        columns += [c for c in df.columns if c not in columns]
    if _id is not None and _id in columns:
        raise DplyrError("bind_rows", f"`_id` ({_id!r}) ya es el nombre de una columna.")

    types: dict[str, pl.DataType] = {}
    for c in columns:
        try:
            types[c] = ptype_common((f"..{i}${c}", df.schema[c])
                                    for i, (_, df, _) in enumerate(unwrapped, 1) if c in df.columns)
        except ExprError as err:
            raise DplyrError("bind_rows", str(err)) from err

    parts = []
    for i, (key, df, _) in enumerate(unwrapped, 1):
        cols = []
        for c in columns:
            if c in df.columns:
                try:
                    cols.append(cast(df.get_column(c), types[c], f"..{i}${c}"))
                except ExprError as err:
                    raise DplyrError("bind_rows", str(err)) from err
            else:
                cols.append(pl.Series(c, [None] * df.height, dtype=types[c]))
        part = pl.DataFrame(cols)
        if _id is not None:
            part = part.select(pl.lit(key).alias(_id), pl.all())
        parts.append(part)
    return rewrap(pl.concat(parts, how="vertical"), groups)


def bind_cols(*frames: Any) -> pl.DataFrame:
    """Une tablas lado a lado. Todas deben tener el mismo número de filas
    (o 1, que se recicla).

    Los nombres repetidos se reparan como en vctrs (``x...1``, ``x...3``, con
    la posición base 1 de la columna) y se informa el cambio.
    """
    dfs: list[pl.DataFrame] = []
    for i, arg in enumerate(frames, 1):
        if isinstance(arg, (list, tuple)):
            for j, sub in enumerate(arg, 1):
                dfs.append(unwrap(sub, "bind_cols", f"..{i}[{j}]")[0])
        elif isinstance(arg, pl.Series):
            dfs.append(arg.to_frame())
        elif arg is not None:
            dfs.append(unwrap(arg, "bind_cols", f"..{i}")[0])
    if not dfs:
        return pl.DataFrame()
    sizes = {df.height for df in dfs} - {1}
    if len(sizes) > 1:
        raise DplyrError("bind_cols", "Todas las tablas deben tener el mismo número de filas "
                                      f"(o 1), pero hay tamaños {sorted(sizes)}.")
    n = sizes.pop() if sizes else 1
    series = [s if len(s) == n else s.new_from_index(0, n)
              for df in dfs for s in df.get_columns()]

    names = [s.name for s in series]
    dup = {nm for nm in names if names.count(nm) > 1}
    if dup:
        changes = []
        for pos, s in enumerate(series, 1):
            if s.name in dup:
                new = f"{s.name}...{pos}"
                changes.append(f"• `{s.name}` -> `{new}`")
                series[pos - 1] = s.alias(new)
        inform("Nombres nuevos:\n" + "\n".join(changes))
    return pl.DataFrame(series)
