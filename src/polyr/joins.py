"""Uniones de tablas con la semántica de dplyr 1.1.

Diferencias con un ``join`` directo de polars que esta capa corrige:

* **NA coincide con NA** por defecto (``na_matches="na"``), como en dplyr.
* **Orden de filas estable**: las filas de ``x`` en su orden original; las
  filas de ``y`` sin pareja (en ``right_join``/``full_join``) al final.
* **Tipos de las claves**: se llevan a su tipo común (``<integer>`` con
  ``<double>`` funciona; ``<character>`` con ``<double>`` es un error).
* Controles de ``multiple``, ``unmatched`` y ``relationship``.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import polars as pl

from ._core import Frame, rewrap, two_table_verb, unwrap
from ._types import ptype_common
from .errors import DplyrError, ExprError, inform
from .expr import BinOp, Col, Lit

__all__ = ["join_by", "inner_join", "left_join", "right_join", "full_join",
           "semi_join", "anti_join", "cross_join", "nest_join", "JoinBy"]

_XR, _YR = "__polyr_x_row__", "__polyr_y_row__"
_RELATIONSHIPS = (None, "one-to-one", "one-to-many", "many-to-one", "many-to-many")


class JoinBy:
    """Especificación de claves creada con :func:`join_by`."""

    def __init__(self, pairs: list[tuple[str, str]]):
        self.pairs = pairs

    def __repr__(self) -> str:
        parts = [a if a == b else f"{a} == {b}" for a, b in self.pairs]
        return f"join_by({', '.join(parts)})"


def join_by(*conditions: Any) -> JoinBy:
    """Claves de unión, como ``dplyr::join_by()``.

    * ``join_by("id")`` o ``join_by(f.id)``: misma columna en ambas tablas.
    * ``join_by(f.id == f.codigo)``: ``id`` de ``x`` con ``codigo`` de ``y``.

    Las uniones por desigualdad, rolling y de solapamiento están en el ROADMAP.
    """
    pairs: list[tuple[str, str]] = []
    for cond in conditions:
        if isinstance(cond, str):
            pairs.append((cond, cond))
        elif isinstance(cond, Col):
            pairs.append((cond.name, cond.name))
        elif isinstance(cond, BinOp) and cond.op == "==" \
                and isinstance(cond.left, Col) and isinstance(cond.right, Col):
            pairs.append((cond.left.name, cond.right.name))
        elif isinstance(cond, BinOp) and isinstance(cond.left, Col) and isinstance(cond.right, (Col, Lit)):
            raise DplyrError("join_by", f"Las uniones por `{cond.op}` todavía no están implementadas "
                            "(ver ROADMAP.md).")
        else:
            raise DplyrError("join_by", f"`{cond!r}` no es una condición válida para `join_by()`.")
    if not pairs:
        raise DplyrError("join_by", "`join_by()` necesita al menos una condición.")
    return JoinBy(pairs)


def _keys(x: pl.DataFrame, y: pl.DataFrame, by: Any, verb_name: str) -> list[tuple[str, str]]:
    if by is None:
        common = [c for c in x.columns if c in y.columns]
        if not common:
            raise DplyrError(verb_name, "`by` es obligatorio cuando `x` e `y` no tienen "
                                        "columnas en común.")
        inform(f"Uniendo con `by = join_by({', '.join(common)})`")
        pairs = [(c, c) for c in common]
    elif isinstance(by, JoinBy):
        pairs = by.pairs
    elif isinstance(by, str):
        pairs = [(by, by)]
    elif isinstance(by, Mapping):
        pairs = [(str(a), str(b)) for a, b in by.items()]
    elif isinstance(by, Sequence) and all(isinstance(b, str) for b in by):
        pairs = [(b, b) for b in by]
    else:
        pairs = join_by(by).pairs
    for side, frame, names in (("x", x, [a for a, _ in pairs]), ("y", y, [b for _, b in pairs])):
        missing = [c for c in names if c not in frame.columns]
        if missing:
            raise DplyrError(verb_name, f"Las columnas de unión de `{side}` deben existir.\n"
                                        f"✖ No existe `{missing[0]}`.")
    return pairs


def _cast_keys(x: pl.DataFrame, y: pl.DataFrame, pairs: list[tuple[str, str]],
               verb_name: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    for a, b in pairs:
        try:
            common = ptype_common([(f"x${a}", x.schema[a]), (f"y${b}", y.schema[b])])
        except ExprError as err:
            msg = str(err).replace("No se puede combinar", "No se puede unir")
            raise DplyrError(verb_name, msg) from err
        if common == pl.Null:
            common = pl.Boolean
        x = x.with_columns(pl.col(a).cast(common))
        y = y.with_columns(pl.col(b).cast(common))
    return x, y


def _check_na_matches(value: str, verb_name: str) -> bool:
    if value not in ("na", "never"):
        raise DplyrError(verb_name, f"`na_matches` debe ser 'na' o 'never', no {value!r}.")
    return value == "na"


def _first_bad(counts: pl.DataFrame, row_col: str) -> int | None:
    bad = counts.filter(pl.col("len") > 1)
    return None if bad.is_empty() else int(bad[row_col].min())


def _mutating_join(x_in: Frame, y_in: Frame, how: str, by: Any, suffix: tuple[str, str],
                   multiple: str, unmatched: str, relationship: str | None,
                   na_matches: str, keep: Any, verb_name: str) -> Frame:
    x, groups = unwrap(x_in, verb_name, "x")
    y, _ = unwrap(y_in, verb_name, "y")
    if keep not in (None, True, False):
        raise DplyrError(verb_name, f"`keep` debe ser True, False o None, no {keep!r}.")
    if multiple not in ("all", "any", "first", "last"):
        raise DplyrError(verb_name, f"`multiple` debe ser 'all', 'any', 'first' o 'last', "
                                    f"no {multiple!r}.")
    if unmatched not in ("drop", "error"):
        raise DplyrError(verb_name, f"`unmatched` debe ser 'drop' o 'error', no {unmatched!r}.")
    if relationship not in _RELATIONSHIPS:
        raise DplyrError(verb_name, f"`relationship` no válido: {relationship!r}.")
    if not (isinstance(suffix, (tuple, list)) and len(suffix) == 2
            and all(isinstance(s, str) for s in suffix)):
        raise DplyrError(verb_name, "`suffix` debe ser una tupla de dos strings.")
    nulls_equal = _check_na_matches(na_matches, verb_name)

    pairs = _keys(x, y, by, verb_name)
    x, y = _cast_keys(x, y, pairs, verb_name)
    xk = [a for a, _ in pairs]
    yk = [b for _, b in pairs]

    # Con `keep=True` las claves de `y` viajan como columnas propias; si no,
    # se funden con las de `x` (y por eso se renombran a los nombres de `x`).
    keep_keys = keep is True
    y_carry = list(y.columns) if keep_keys else [c for c in y.columns if c not in yk]
    conflicts = set(x.columns) & set(y_carry)
    x_names = {c: (c + suffix[0] if c in conflicts and (keep_keys or c not in xk) else c)
               for c in x.columns}
    y_names = {c: (c + suffix[1] if c in conflicts else c) for c in y_carry}

    xd = x.rename(x_names).with_row_index(_XR)
    left_on = [x_names[a] for a in xk]
    if keep_keys:
        yd = y.select(y_carry).rename(y_names).with_row_index(_YR)
        right_on = [y_names[b] for b in yk]
    else:
        yd = (y.select(yk + y_carry).rename(y_names)
              .rename({b: a for a, b in pairs if a != b}).with_row_index(_YR))
        right_on = left_on

    def _join(left: pl.DataFrame, right: pl.DataFrame, how: str) -> pl.DataFrame:
        if left_on == right_on:
            return left.join(right, on=left_on, how=how, nulls_equal=nulls_equal,
                             coalesce=True, maintain_order="none")
        return left.join(right, left_on=left_on, right_on=right_on, how=how,
                         nulls_equal=nulls_equal, coalesce=not keep_keys,
                         maintain_order="none")

    # --- controles previos: relationship, multiple, unmatched -------------------
    matches = _join(xd.select([_XR] + left_on), yd.select([_YR] + right_on), "inner")
    x_counts = matches.group_by(_XR).len()
    y_counts = matches.group_by(_YR).len()
    x_multi = _first_bad(x_counts, _XR)
    y_multi = _first_bad(y_counts, _YR)
    if relationship in ("one-to-one", "many-to-one") and x_multi is not None:
        raise DplyrError(verb_name, "Cada fila de `x` debe coincidir con 1 fila de `y` como máximo.\n"
                                    f"ℹ La fila {x_multi} de `x` coincide con varias filas de `y`.")
    if relationship in ("one-to-one", "one-to-many") and y_multi is not None:
        raise DplyrError(verb_name, "Cada fila de `y` debe coincidir con 1 fila de `x` como máximo.\n"
                                    f"ℹ La fila {y_multi} de `y` coincide con varias filas de `x`.")
    if relationship is None and x_multi is not None and y_multi is not None and multiple == "all":
        import warnings
        warnings.warn(
            f"`{verb_name}()`: se detectó una relación muchos-a-muchos inesperada entre `x` e `y`.\n"
            f"ℹ La fila {x_multi} de `x` coincide con varias filas de `y`, y la fila {y_multi} "
            f"de `y` coincide con varias filas de `x`.\n"
            "ℹ Si es intencional, usa `relationship=\"many-to-many\"`.",
            UserWarning, stacklevel=4,
        )
    if unmatched == "error":
        checks = {"inner": ("x", "y"), "left": ("y",), "right": ("x",), "full": ()}[how]
        for side in checks:
            rows, counts, total = ((_XR, x_counts, x.height) if side == "x"
                                   else (_YR, y_counts, y.height))
            matched = set(counts[rows].to_list())
            missing = next((i for i in range(total) if i not in matched), None)
            if missing is not None:
                other = "y" if side == "x" else "x"
                raise DplyrError(verb_name, f"Cada fila de `{side}` debe tener pareja en `{other}`.\n"
                                            f"ℹ La fila {missing} de `{side}` no tiene pareja.")

    # --- unión ----------------------------------------------------------------
    polars_how = {"inner": "inner", "left": "left", "right": "full", "full": "full"}[how]
    joined = _join(xd, yd, polars_how)
    if how == "right":
        joined = joined.filter(pl.col(_YR).is_not_null())
    joined = joined.sort([_XR, _YR], nulls_last=True, maintain_order=True)

    if multiple != "all":
        pick = pl.col(_YR).max() if multiple == "last" else pl.col(_YR).min()
        keep_rows = pl.col(_XR).is_null() | pl.col(_YR).is_null() | (pl.col(_YR) == pick.over(_XR))
        joined = joined.filter(keep_rows)

    out = joined.select([x_names[c] for c in x.columns] + [y_names[c] for c in y_carry])
    return rewrap(out, [x_names.get(g, g) for g in groups])


def _join_doc(how: str) -> str:
    return {
        "inner": "Filas de ``x`` con pareja en ``y``.",
        "left": "Todas las filas de ``x``; columnas de ``y`` donde hay pareja.",
        "right": "Todas las filas de ``y``; las que no tienen pareja en ``x`` van al final.",
        "full": "Todas las filas de ``x`` y de ``y``.",
    }[how]


def _make_join(how: str):
    def join(x: Frame, y: Frame, /, by: Any = None, suffix: tuple[str, str] = (".x", ".y"),
             multiple: str = "all", unmatched: str = "drop", relationship: str | None = None,
             na_matches: str = "na", keep: Any = None) -> Frame:
        return _mutating_join(x, y, how, by, tuple(suffix), multiple, unmatched,
                              relationship, na_matches, keep, f"{how}_join")
    join.__name__ = f"{how}_join"
    join.__qualname__ = join.__name__
    join.__doc__ = f"""{_join_doc(how)}

    Parámetros como en dplyr: ``by`` (``None`` = columnas en común, con
    mensaje), ``suffix``, ``multiple`` (``"all"``, ``"any"``, ``"first"``,
    ``"last"``), ``unmatched`` (``"drop"``, ``"error"``), ``relationship``
    (``None``, ``"one-to-one"``, ``"one-to-many"``, ``"many-to-one"``,
    ``"many-to-many"``) y ``na_matches`` (``"na"``, ``"never"``).
    Los índices de fila en los mensajes son base 0.

    ``keep=True`` conserva las columnas de clave de las dos tablas en lugar de
    fundirlas en una; si se llaman igual, reciben los sufijos de ``suffix``.
    """
    return two_table_verb(join)


inner_join = _make_join("inner")
left_join = _make_join("left")
right_join = _make_join("right")
full_join = _make_join("full")


def _filtering_join(x_in: Frame, y_in: Frame, by: Any, na_matches: str, anti: bool,
                    verb_name: str) -> Frame:
    x, groups = unwrap(x_in, verb_name, "x")
    y, _ = unwrap(y_in, verb_name, "y")
    nulls_equal = _check_na_matches(na_matches, verb_name)
    pairs = _keys(x, y, by, verb_name)
    xc, yc = _cast_keys(x, y, pairs, verb_name)
    xk = [a for a, _ in pairs]
    yd = yc.select([b for _, b in pairs]).rename({b: a for a, b in pairs if a != b}).unique()
    xd = xc.select(xk).with_row_index(_XR)
    hits = xd.join(yd, on=xk, how="anti" if anti else "semi", nulls_equal=nulls_equal)
    rows = hits.get_column(_XR).sort()
    return rewrap(x[rows], groups)


@two_table_verb
def semi_join(x: Frame, y: Frame, /, by: Any = None, na_matches: str = "na") -> Frame:
    """Filas de ``x`` que tienen pareja en ``y`` (sin duplicar ni agregar columnas)."""
    return _filtering_join(x, y, by, na_matches, False, "semi_join")


@two_table_verb
def anti_join(x: Frame, y: Frame, /, by: Any = None, na_matches: str = "na") -> Frame:
    """Filas de ``x`` que **no** tienen pareja en ``y``."""
    return _filtering_join(x, y, by, na_matches, True, "anti_join")


@two_table_verb
def cross_join(x: Frame, y: Frame, /, suffix: tuple[str, str] = (".x", ".y")) -> Frame:
    """Todas las combinaciones de filas de ``x`` e ``y``."""
    xd, groups = unwrap(x, "cross_join", "x")
    yd, _ = unwrap(y, "cross_join", "y")
    conflicts = set(xd.columns) & set(yd.columns)
    xr = xd.rename({c: c + suffix[0] for c in conflicts})
    yr = yd.rename({c: c + suffix[1] for c in conflicts})
    out = xr.join(yr, how="cross", maintain_order="left_right")
    return rewrap(out, [g + suffix[0] if g in conflicts else g for g in groups])


@two_table_verb
def nest_join(x: Frame, y: Frame, /, by: Any = None, keep: Any = None,
              na_matches: str = "na", name: str = "y") -> Frame:
    """Agrega a ``x`` una columna con las filas de ``y`` que le corresponden.

    Es el ``nest_join()`` de dplyr: en vez de repetir las filas de ``x`` una
    vez por pareja, guarda todas las parejas juntas en una sola celda. En
    polars esa celda es una lista de structs:
    ``out["y"][0].struct.unnest()`` reconstruye, como tabla, las filas de
    ``y`` que corresponden a la primera fila de ``x``.

    * ``x`` conserva su número de filas y su orden; sin parejas, la celda
      queda vacía.
    * La columna nueva se llama ``y``; usa ``name=`` para cambiarlo (en R el
      nombre sale del argumento, que en Python no se puede leer).
    * ``keep=True`` guarda también las columnas de clave de ``y``.
    """
    xf, groups = unwrap(x, "nest_join", "x")
    yf, _ = unwrap(y, "nest_join", "y")
    if keep not in (None, True, False):
        raise DplyrError("nest_join", f"`keep` debe ser True, False o None, no {keep!r}.")
    if not isinstance(name, str) or not name:
        raise DplyrError("nest_join", "`name` debe ser el nombre de la columna nueva.")
    if name in xf.columns:
        raise DplyrError("nest_join", f"`{name}` ya es una columna de `x`.\n"
                                      "ℹ Usa `name=` para elegir otro nombre.")
    nulls_equal = _check_na_matches(na_matches, "nest_join")
    pairs = _keys(xf, yf, by, "nest_join")
    xc, yc = _cast_keys(xf, yf, pairs, "nest_join")
    xk = [a for a, _ in pairs]
    yk = [b for _, b in pairs]
    nested = list(yc.columns) if keep is True else [c for c in yc.columns if c not in yk]

    cell = pl.struct([pl.col(c) for c in nested]) if nested else pl.struct(pl.lit(0).alias("_"))
    keyed = yc.select([pl.col(b).alias(a) for a, b in pairs] + [cell.alias(name)])
    grouped = keyed.group_by(xk, maintain_order=True).agg(pl.col(name))
    out = xc.join(grouped, on=xk, how="left", nulls_equal=nulls_equal,
                  coalesce=True, maintain_order="left")
    # Sin parejas, dplyr deja una tabla de 0 filas, no un faltante.
    vacia = pl.lit([], dtype=grouped.schema[name])
    return rewrap(out.with_columns(pl.col(name).fill_null(vacia)), groups)
