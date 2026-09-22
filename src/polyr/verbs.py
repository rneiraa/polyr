"""Verbos de una tabla que conservan una fila por fila (o la filtran).

Todos funcionan con llamada directa o con el pipe ``>>``, y aceptan un
``polars.DataFrame`` o un :class:`~polyr.grouped.GroupedFrame`.

Convenciones (ver ``docs/diferencias-con-dplyr.md``):

* El data frame es un argumento *solo posicional*: una columna puede
  llamarse ``data`` sin conflicto.
* Los argumentos que en dplyr empiezan con punto (``.keep``, ``.by``) aquí
  empiezan con guion bajo (``_keep``, ``_by``).
"""
from __future__ import annotations

from typing import Any, Callable

import polars as pl

from . import _types
from ._core import (Frame, anchors, evaluate, recycle, reject_named, relocate_order,
                    resolve_by, resolve_cols, rewrap, select_cols, unwrap, verb)
from .across import Across
from .errors import DplyrError, ExprError, inform
from .expr import Col, Lit, wrap
from .functions import Desc
from .grouped import GroupedFrame
from .tidyselect import check_unique, everything

__all__ = ["filter", "mutate", "select", "rename", "rename_with", "relocate", "arrange",
           "pull", "distinct", "group_by", "ungroup", "group_vars", "n_groups", "group_keys"]


# --- filter -------------------------------------------------------------------

@verb
def filter(data: Frame, /, *conditions: Any, _by: Any = None, **named: Any) -> Frame:
    """Conserva las filas donde todas las condiciones son TRUE.

    * Varias condiciones se combinan con ``&``.
    * Las filas donde la condición es NA se descartan.
    * Con grupos, las condiciones se evalúan dentro de cada grupo
      (``f.x > mean(f.x)`` compara con la media del grupo).
    """
    df, groups = unwrap(data, "filter")
    keys, _ = resolve_by(df, groups, _by, "filter")
    if named:
        name, value = next(iter(named.items()))
        raise DplyrError(
            "filter",
            f"Se detectó un argumento con nombre (`{name}=`). Los argumentos de "
            f"`filter()` no llevan nombre.\nℹ ¿Quisiste decir `f.{name} == {wrap(value)!r}`?",
        )

    n = df.height
    mask: pl.Series | None = None
    for i, cond in enumerate(conditions, start=1):
        expr = wrap(cond)
        label = repr(expr)
        s = evaluate(df, expr, "filter", label, keys)
        if s.dtype == pl.Null:  # un NA suelto es un lógico válido, como en R
            s = s.cast(pl.Boolean)
        if s.dtype != pl.Boolean:
            raise DplyrError(
                "filter",
                f"La condición {i} debe ser un vector lógico, no {_types.type_name(s.dtype)}.",
                label,
            )
        s = recycle(s, n, "filter", label, f"La condición {i}")
        mask = s if mask is None else (mask & s)  # lógica de tres valores, igual que R

    out = df if mask is None else df.filter(mask)
    return rewrap(out, groups)


# --- mutate -------------------------------------------------------------------

_KEEP = ("all", "used", "unused", "none")


def _expand_items(df: pl.DataFrame, positional: tuple, named: dict, keys: list[str],
                  verb_name: str) -> list[tuple[str, Any]]:
    """Normaliza los argumentos de mutate/summarise a pares (nombre, valor).

    ``across()`` se deja sin expandir: se expande en su turno, para que vea
    las columnas creadas antes.
    """
    items: list[tuple[str, Any]] = []
    for arg in positional:
        if isinstance(arg, Across):
            items.append(("", arg))
        else:
            raise DplyrError(
                verb_name,
                f"Los argumentos de `{verb_name}()` deben tener nombre (salvo `across()`).\n"
                f"ℹ Por ejemplo: {verb_name}(nueva={wrap(arg)!r}).",
            )
    items.extend(named.items())
    return items


def _across_items(df: pl.DataFrame, item: Across, keys: list[str], verb_name: str
                  ) -> list[tuple[str, Any]]:
    try:
        return item.expand(df, exclude=keys)
    except ExprError as err:
        raise DplyrError(verb_name, str(err), repr(item)) from err


@verb
def mutate(data: Frame, /, *args: Any, _keep: str = "all", _before: Any = None,
           _after: Any = None, _by: Any = None, **new_columns: Any) -> Frame:
    """Crea, modifica o elimina columnas.

    * Se evalúa en orden: cada columna puede usar las creadas antes.
    * ``col=None`` elimina la columna; ``col=NA`` la llena de NA.
    * Con grupos (o ``_by``), cada expresión se evalúa dentro de su grupo.
    * ``_keep``: ``"all"`` (defecto), ``"used"``, ``"unused"`` o ``"none"``.
    * ``_before`` / ``_after``: dónde ubicar las columnas **nuevas**.
    * Admite ``across()`` como argumento posicional.
    """
    df, groups = unwrap(data, "mutate")
    keys, _ = resolve_by(df, groups, _by, "mutate")
    if _keep not in _KEEP:
        raise DplyrError("mutate", f"`_keep` debe ser uno de {', '.join(map(repr, _KEEP))}, "
                                   f"no {_keep!r}.")
    before, after = anchors(df, _before, _after, "mutate")
    items = _expand_items(df, args, new_columns, keys, "mutate")

    original = list(df.columns)
    used: set[str] = set()
    touched: list[str] = []  # columnas creadas o modificadas, en orden
    out = df
    queue = list(items)
    while queue:
        name, value = queue.pop(0)
        if isinstance(value, Across):
            queue = _across_items(out, value, keys, "mutate") + queue
            continue
        if value is None:
            if name in keys:
                raise DplyrError("mutate", f"No se puede eliminar la variable de agrupación `{name}`.")
            if name in out.columns:
                out = out.drop(name)
            touched = [t for t in touched if t != name]
            continue
        expr = wrap(value)
        label = f"{name} = {expr!r}"
        used |= expr.columns() & (set(original) - set(touched))
        s = evaluate(out, expr, "mutate", label, keys)
        s = recycle(s, out.height, "mutate", label, f"`{name}`").alias(name)
        out = out.with_columns(s)  # si ya existe, conserva su posición
        if name not in touched:
            touched.append(name)

    if _keep != "all":
        touched_set, key_set = set(touched), set(keys)

        def keep(c: str) -> bool:
            if c in touched_set or c in key_set:
                return True
            if _keep == "used":
                return c in used
            if _keep == "unused":
                return c not in used
            return False
        out = out.select([c for c in out.columns if keep(c)])

    created = [c for c in touched if c not in original and c in out.columns]
    if created and (before is not None or after is not None):
        out = out.select(relocate_order(out.columns, created, before, after))
    return rewrap(out, groups)


# --- select / rename / relocate -----------------------------------------------

def _rename_groups(groups: list[str], mapping: dict[str, str]) -> list[str]:
    return [mapping.get(g, g) for g in groups]


@verb
def select(data: Frame, /, *args: Any, **named: Any) -> Frame:
    """Selecciona (y opcionalmente renombra) columnas con tidyselect.

    ``select(df, f.id, starts_with("x"), nuevo=f.viejo)``

    Con grupos, las variables de agrupación se conservan siempre (se agregan
    al principio con un mensaje si no se seleccionaron).
    """
    df, groups = unwrap(data, "select")
    selection = select_cols(df, args, named, "select")
    missing = [g for g in groups if g not in selection]
    if missing:
        inform("Agregando variables de agrupación faltantes: "
               + ", ".join(f"`{g}`" for g in missing))
        selection = {**{g: g for g in missing}, **selection}
        try:
            check_unique(selection.values())
        except ExprError as err:
            raise DplyrError("select", str(err)) from err
    out = df.select([pl.col(old).alias(new) for old, new in selection.items()])
    return rewrap(out, _rename_groups(groups, selection))


@verb
def rename(data: Frame, /, *args: Any, **named: Any) -> Frame:
    """Renombra columnas sin cambiar el resto: ``rename(df, nuevo=f.viejo)``."""
    df, groups = unwrap(data, "rename")
    if args:
        raise DplyrError("rename", "Todos los argumentos de `rename()` deben tener nombre.\n"
                                   "ℹ Usa rename(nuevo=f.viejo).")
    mapping = select_cols(df, [], named, "rename")
    return _apply_rename(df, groups, mapping, "rename")


def _apply_rename(df: pl.DataFrame, groups: list[str], mapping: dict[str, str],
                  verb_name: str) -> Frame:
    final = [mapping.get(c, c) for c in df.columns]
    try:
        check_unique(final)
    except ExprError as err:
        raise DplyrError(verb_name, str(err)) from err
    out = df.rename({o: n for o, n in mapping.items() if o != n})
    return rewrap(out, _rename_groups(groups, mapping))


@verb
def rename_with(data: Frame, /, fn: Callable[[str], str], cols: Any = None) -> Frame:
    """Renombra con una función: ``rename_with(df, str.upper, starts_with("x"))``."""
    df, groups = unwrap(data, "rename_with")
    if not callable(fn):
        raise DplyrError("rename_with", "`fn` debe ser una función que reciba y devuelva un string.")
    selected = resolve_cols(everything() if cols is None else cols, df, "rename_with", "cols")
    mapping = {}
    for c in selected:
        new = fn(c)
        if not isinstance(new, str):
            raise DplyrError("rename_with", f"`fn` debe devolver un string, no "
                                            f"`{type(new).__name__}` (columna `{c}`).")
        mapping[c] = new
    return _apply_rename(df, groups, mapping, "rename_with")


@verb
def relocate(data: Frame, /, *args: Any, _before: Any = None, _after: Any = None,
             **named: Any) -> Frame:
    """Cambia la posición de columnas (por defecto, al principio).

    ``relocate(df, f.z, _after=f.x)``; también admite renombrar: ``nuevo=f.z``.
    """
    df, groups = unwrap(data, "relocate")
    selection = select_cols(df, args, named, "relocate")
    before, after = anchors(df, _before, _after, "relocate")
    order = relocate_order(df.columns, list(selection), before, after)
    try:
        check_unique([selection.get(c, c) for c in order])
    except ExprError as err:
        raise DplyrError("relocate", str(err)) from err
    out = df.select([pl.col(c).alias(selection.get(c, c)) for c in order])
    return rewrap(out, _rename_groups(groups, selection))


# --- arrange ------------------------------------------------------------------

def sort_frame(df: pl.DataFrame, keys: tuple[Any, ...], verb_name: str,
               prefix_groups: list[str] | None = None) -> pl.DataFrame:
    """Ordenamiento con la semántica de dplyr (NA al final, estable, locale C)."""
    n = df.height
    sort_cols, descending = [], []
    for g in prefix_groups or []:
        sort_cols.append(df.get_column(g).alias(f"__g_{len(sort_cols)}__"))
        descending.append(False)
    for key in keys:
        node = wrap(key)
        is_desc = isinstance(node, Desc)
        inner = node.inner if is_desc else node
        label = repr(node)
        s = evaluate(df, inner, verb_name, label)
        s = recycle(s, n, verb_name, label, f"La clave `{label}`")
        if s.dtype.is_float():
            s = s.fill_nan(None)
        sort_cols.append(s.alias(f"__k_{len(sort_cols)}__"))
        descending.append(is_desc)
    if not sort_cols:
        return df
    keyed = df.with_columns(sort_cols)
    names = [s.name for s in sort_cols]
    return keyed.sort(names, descending=descending, nulls_last=True,
                      maintain_order=True).drop(names)


@verb
def arrange(data: Frame, /, *keys: Any, _by_group: bool = False, **named: Any) -> Frame:
    """Ordena filas por una o más claves; ``desc()`` para orden descendente.

    * Los NA (y NaN) van **siempre al final**, también con ``desc()``.
    * El orden es estable: los empates conservan el orden original.
    * Los strings se ordenan en el locale "C" (por bytes).
    * Las claves pueden ser expresiones: ``arrange(df, f.x + f.y)``.
    * Ignora los grupos, salvo con ``_by_group=True``.
    """
    df, groups = unwrap(data, "arrange")
    reject_named("arrange", named, "\nℹ `arrange()` no acepta argumentos con nombre.")
    out = sort_frame(df, keys, "arrange", groups if _by_group else None)
    return rewrap(out, groups)


# --- pull / distinct ----------------------------------------------------------

@verb
def pull(data: Frame, /, var: Any = None) -> pl.Series:
    """Extrae una columna como Series. Por defecto, la última (como dplyr)."""
    df, _ = unwrap(data, "pull")
    if var is None:
        if df.width == 0:
            raise DplyrError("pull", "El data frame no tiene columnas.")
        return df.get_column(df.columns[-1])
    found = resolve_cols(var, df, "pull", repr(wrap(var)))
    if len(found) != 1:
        raise DplyrError("pull", f"`var` debe seleccionar exactamente una columna, no {len(found)}.")
    return df.get_column(found[0])


def _key_columns(df: pl.DataFrame, groups: list[str], args: tuple, named: dict,
                 verb_name: str) -> tuple[pl.DataFrame, list[str]]:
    """Columnas clave para distinct/count/group_by: nombres o expresiones con nombre."""
    names: list[str] = []
    for arg in args:
        node = wrap(arg)
        if isinstance(node, Col) or (isinstance(node, Lit) and isinstance(node.value, str)):
            name = node.name if isinstance(node, Col) else node.value
            if name not in df.columns:
                raise DplyrError(verb_name, f"No se encontró la columna `{name}`.", repr(node))
            names.append(name)
        else:
            raise DplyrError(
                verb_name,
                f"Las expresiones en `{verb_name}()` deben tener nombre.\n"
                f"ℹ Por ejemplo: {verb_name}(nueva={node!r}).",
                repr(node),
            )
    if named:
        computed = mutate(rewrap(df, groups), **named)
        df = computed.data if isinstance(computed, GroupedFrame) else computed
        names.extend(named)
    return df, list(dict.fromkeys(names))


@verb
def distinct(data: Frame, /, *args: Any, _keep_all: bool = False, **named: Any) -> Frame:
    """Filas únicas (la primera aparición de cada combinación).

    * Sin argumentos, usa todas las columnas.
    * Con columnas, devuelve solo esas (más los grupos), salvo ``_keep_all=True``.
    * NA se considera igual a NA.
    """
    df, groups = unwrap(data, "distinct")
    df, cols = _key_columns(df, groups, args, named, "distinct")
    if not cols:
        return rewrap(df.unique(keep="first", maintain_order=True), groups)
    subset = list(dict.fromkeys(groups + cols))
    out = df.unique(subset=subset, keep="first", maintain_order=True)
    if not _keep_all:
        out = out.select(subset)
    return rewrap(out, groups)


# --- agrupación ---------------------------------------------------------------

@verb
def group_by(data: Frame, /, *args: Any, _add: bool = False, **named: Any) -> Frame:
    """Agrupa por columnas existentes o calculadas: ``group_by(df, f.a, grande=f.x > 10)``.

    Por defecto reemplaza los grupos existentes; ``_add=True`` los agrega.
    Los grupos se ordenan como en dplyr (orden ascendente, NA al final) en los
    resultados de ``summarise()``; ``mutate()`` y ``filter()`` conservan el
    orden de las filas.
    """
    df, groups = unwrap(data, "group_by")
    df, cols = _key_columns(df, [], args, named, "group_by")
    new_groups = list(dict.fromkeys((groups if _add else []) + cols))
    return rewrap(df, new_groups)


@verb
def ungroup(data: Frame, /, *args: Any) -> Frame:
    """Quita todos los grupos, o solo los seleccionados: ``ungroup(df, f.a)``."""
    df, groups = unwrap(data, "ungroup")
    if not args:
        return df
    remove: set[str] = set()
    for arg in args:
        remove |= set(resolve_cols(arg, df, "ungroup", repr(wrap(arg))))
    return rewrap(df, [g for g in groups if g not in remove])


def group_vars(data: Frame) -> list[str]:
    """Nombres de las variables de agrupación (lista vacía si no hay grupos)."""
    return data.groups if isinstance(data, GroupedFrame) else []


def n_groups(data: Frame) -> int:
    """Número de grupos (1 si no hay grupos)."""
    return data.n_groups if isinstance(data, GroupedFrame) else 1


def group_keys(data: Frame) -> pl.DataFrame:
    """Una fila por grupo, en el orden de dplyr."""
    if isinstance(data, GroupedFrame):
        return data.group_keys()
    return pl.DataFrame()

