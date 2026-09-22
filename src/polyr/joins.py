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
from .functions import Between

__all__ = ["join_by", "closest", "within", "overlaps", "inner_join", "left_join",
           "right_join", "full_join", "semi_join", "anti_join", "cross_join",
           "nest_join", "JoinBy", "JoinCondition"]

_XR, _YR = "__polyr_x_row__", "__polyr_y_row__"
_RELATIONSHIPS = (None, "one-to-one", "one-to-many", "many-to-one", "many-to-many")
_INEQ = (">=", ">", "<=", "<")
_BOUNDS = ("[]", "[)", "(]", "()")
_HAS_JOIN_WHERE = hasattr(pl.DataFrame, "join_where")


class JoinCondition:
    """Una condición de unión: una columna de ``x`` comparada con una de ``y``."""

    def __init__(self, op: str, left: str, right: str, nearest: bool = False):
        self.op, self.left, self.right, self.nearest = op, left, right, nearest

    def __repr__(self) -> str:
        if self.op == "==" and self.left == self.right:
            return self.left
        text = f"{self.left} {self.op} {self.right}"
        return f"closest({text})" if self.nearest else text


class JoinBy:
    """Especificación de unión creada con :func:`join_by`."""

    def __init__(self, conditions: list[JoinCondition]):
        self.conditions = conditions

    @property
    def pairs(self) -> list[tuple[str, str]]:
        """Solo las condiciones de igualdad, como pares ``(x, y)``."""
        return [(c.left, c.right) for c in self.conditions if c.op == "=="]

    def __repr__(self) -> str:
        return f"join_by({', '.join(repr(c) for c in self.conditions)})"


def _column(value: Any, who: str) -> str:
    if isinstance(value, Col):
        return value.name
    if isinstance(value, str):
        return value
    raise DplyrError(who, f"`{value!r}` no es una columna: usa `f.nombre` o \"nombre\".")


def _bounds_ops(bounds: str, who: str) -> tuple[str, str]:
    if bounds not in _BOUNDS:
        raise DplyrError(who, f"`bounds` debe ser uno de {', '.join(map(repr, _BOUNDS))}, "
                              f"no {bounds!r}.")
    return (">=" if bounds[0] == "[" else ">", "<=" if bounds[1] == "]" else "<")


def _as_conditions(cond: Any) -> list[JoinCondition]:
    """Traduce un argumento de ``join_by()`` a condiciones."""
    if isinstance(cond, JoinCondition):
        return [cond]
    if isinstance(cond, (list, tuple)):
        return [c for item in cond for c in _as_conditions(item)]
    if isinstance(cond, str):
        return [JoinCondition("==", cond, cond)]
    if isinstance(cond, Col):
        return [JoinCondition("==", cond.name, cond.name)]
    if isinstance(cond, Between):
        x, lo, hi = (_column(a, "join_by") for a in cond.args)
        op_lo, op_hi = _bounds_ops(cond.bounds, "join_by")
        return [JoinCondition(op_lo, x, lo), JoinCondition(op_hi, x, hi)]
    if isinstance(cond, BinOp) and cond.op in ("==",) + _INEQ \
            and isinstance(cond.left, Col) and isinstance(cond.right, Col):
        return [JoinCondition(cond.op, cond.left.name, cond.right.name)]
    if isinstance(cond, BinOp) and isinstance(cond.right, Lit):
        raise DplyrError("join_by", f"`{cond!r}` compara una columna con un valor fijo.\n"
                                    "ℹ Las dos partes deben ser columnas: la izquierda de `x` "
                                    "y la derecha de `y`.")
    raise DplyrError("join_by", f"`{cond!r}` no es una condición válida para `join_by()`.")


def join_by(*conditions: Any) -> JoinBy:
    """Cómo se emparejan las filas, como ``dplyr::join_by()``.

    * ``join_by("id")`` o ``join_by(f.id)``: misma columna en ambas tablas.
    * ``join_by(f.id == f.codigo)``: ``id`` de ``x`` con ``codigo`` de ``y``.
    * Desigualdades: ``join_by(f.fecha >= f.inicio, f.fecha < f.fin)``.
    * Rangos: ``join_by(between(f.fecha, f.inicio, f.fin))``,
      :func:`within`, :func:`overlaps`.
    * La pareja más cercana: ``join_by(closest(f.fecha >= f.corte))``.

    La izquierda de cada condición siempre es una columna de ``x`` y la
    derecha una de ``y``. Se pueden combinar: ``join_by(f.g, closest(f.t >= f.t0))``.
    """
    out = [c for cond in conditions for c in _as_conditions(cond)]
    if not out:
        raise DplyrError("join_by", "`join_by()` necesita al menos una condición.")
    return JoinBy(out)


def closest(condition: Any) -> JoinCondition:
    """Solo la pareja más cercana, como ``dplyr::closest()``.

    ``closest(f.fecha >= f.corte)`` se queda, de todas las filas de ``y`` que
    cumplen la desigualdad, con las del ``corte`` más grande (con ``<=`` o
    ``<``, con el más chico). Los empates se conservan todos.
    """
    conds = _as_conditions(condition)
    if len(conds) != 1 or conds[0].op not in _INEQ:
        raise DplyrError("closest", "`closest()` necesita una sola desigualdad, "
                                    "como `closest(f.x >= f.y)`.")
    c = conds[0]
    return JoinCondition(c.op, c.left, c.right, nearest=True)


def within(x_lower: Any, x_upper: Any, y_lower: Any, y_upper: Any) -> list[JoinCondition]:
    """El rango de ``x`` cabe dentro del de ``y``.

    Equivale a ``x_lower >= y_lower`` y ``x_upper <= y_upper``.
    """
    xl, xu, yl, yu = (_column(v, "within") for v in (x_lower, x_upper, y_lower, y_upper))
    return [JoinCondition(">=", xl, yl), JoinCondition("<=", xu, yu)]


def overlaps(x_lower: Any, x_upper: Any, y_lower: Any, y_upper: Any,
             bounds: str = "[]") -> list[JoinCondition]:
    """Los rangos de ``x`` e ``y`` se solapan.

    Equivale a ``x_lower <= y_upper`` y ``x_upper >= y_lower``. ``bounds``
    decide si los extremos cuentan: ``"[]"`` (por defecto), ``"[)"``,
    ``"(]"`` o ``"()"``.
    """
    xl, xu, yl, yu = (_column(v, "overlaps") for v in (x_lower, x_upper, y_lower, y_upper))
    op_lower, op_upper = _bounds_ops(bounds, "overlaps")
    # El extremo cerrado de `y` es el que decide cada comparación.
    return [JoinCondition("<=" if op_upper == "<=" else "<", xl, yu),
            JoinCondition(">=" if op_lower == ">=" else ">", xu, yl)]


def _keys(x: pl.DataFrame, y: pl.DataFrame, by: Any, verb_name: str) -> list[JoinCondition]:
    if by is None:
        common = [c for c in x.columns if c in y.columns]
        if not common:
            raise DplyrError(verb_name, "`by` es obligatorio cuando `x` e `y` no tienen "
                                        "columnas en común.")
        inform(f"Uniendo con `by = join_by({', '.join(common)})`")
        conds = [JoinCondition("==", c, c) for c in common]
    elif isinstance(by, JoinBy):
        conds = by.conditions
    elif isinstance(by, str):
        conds = [JoinCondition("==", by, by)]
    elif isinstance(by, Mapping):
        conds = [JoinCondition("==", str(a), str(b)) for a, b in by.items()]
    elif isinstance(by, Sequence) and all(isinstance(b, str) for b in by):
        conds = [JoinCondition("==", b, b) for b in by]
    else:
        conds = join_by(by).conditions
    for side, frame, names in (("x", x, [c.left for c in conds]),
                               ("y", y, [c.right for c in conds])):
        missing = [c for c in names if c not in frame.columns]
        if missing:
            raise DplyrError(verb_name, f"Las columnas de unión de `{side}` deben existir.\n"
                                        f"✖ No existe `{missing[0]}`.")
    return conds


def _cast_keys(x: pl.DataFrame, y: pl.DataFrame, conds: list[JoinCondition],
               verb_name: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    for c in conds:
        a, b = c.left, c.right
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


def _predicate(i: int, c: JoinCondition) -> pl.Expr:
    left, right = pl.col(f"__x{i}"), pl.col(f"__y{i}")
    return {">=": left >= right, ">": left > right,
            "<=": left <= right, "<": left < right}[c.op]


def _match_pairs(x: pl.DataFrame, y: pl.DataFrame, conds: list[JoinCondition],
                 nulls_equal: bool) -> pl.DataFrame:
    """Todas las parejas ``(fila de x, fila de y)`` que cumplen las condiciones."""
    xs = x.select([pl.col(c.left).alias(f"__x{i}") for i, c in enumerate(conds)]) \
        .with_row_index(_XR)
    ys = y.select([pl.col(c.right).alias(f"__y{i}") for i, c in enumerate(conds)]) \
        .with_row_index(_YR)
    eq = [i for i, c in enumerate(conds) if c.op == "=="]
    rest = [i for i, c in enumerate(conds) if c.op != "=="]

    if eq:
        cand = xs.join(ys, left_on=[f"__x{i}" for i in eq], right_on=[f"__y{i}" for i in eq],
                       how="inner", nulls_equal=nulls_equal, coalesce=False,
                       maintain_order="none")
        for i in rest:
            cand = cand.filter(_predicate(i, conds[i]))
    elif _HAS_JOIN_WHERE:
        cand = xs.join_where(ys, *[_predicate(i, conds[i]) for i in rest])
    else:  # pragma: no cover - polars antiguo
        cand = xs.join(ys, how="cross")
        for i in rest:
            cand = cand.filter(_predicate(i, conds[i]))

    for i, c in enumerate(conds):
        if not c.nearest:
            continue
        value = pl.col(f"__y{i}")
        target = value.max() if c.op in (">=", ">") else value.min()
        cand = cand.filter(value == target.over(_XR))
    return cand.select([_XR, _YR]).sort([_XR, _YR], maintain_order=True)


def _row_pairs(matches: pl.DataFrame, x_rows: pl.DataFrame, y_rows: pl.DataFrame,
               how: str) -> pl.DataFrame:
    """Parejas de la salida, incluidas las filas sin pareja que el tipo de unión pide."""
    parts = [matches]
    if how in ("left", "full"):
        parts.append(x_rows.join(matches.select(_XR), on=_XR, how="anti")
                     .with_columns(pl.lit(None, dtype=matches.schema[_YR]).alias(_YR)))
    if how in ("right", "full"):
        parts.append(y_rows.join(matches.select(_YR), on=_YR, how="anti")
                     .with_columns(pl.lit(None, dtype=matches.schema[_XR]).alias(_XR)))
    out = pl.concat([p.select([_XR, _YR]) for p in parts])
    return out.sort([_XR, _YR], nulls_last=True, maintain_order=True)


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

    conds = _keys(x, y, by, verb_name)
    x, y = _cast_keys(x, y, conds, verb_name)
    equalities = [c for c in conds if c.op == "=="]
    if keep is False and len(equalities) != len(conds):
        raise DplyrError(verb_name, "`keep=False` no se puede usar con condiciones de "
                                    "desigualdad: no hay una sola columna que conservar.\n"
                                    "ℹ Usa `keep=True` o déjalo sin especificar.")

    # Con `keep=True` las claves de `y` viajan como columnas propias. Si no, las
    # de igualdad se funden con las de `x`; las de desigualdad se conservan,
    # igual que en dplyr, porque no hay un único valor que represente a las dos.
    keep_keys = keep is True
    merged = [] if keep_keys else [c.right for c in equalities]
    y_carry = [c for c in y.columns if c not in merged]
    x_equal = {c.left for c in equalities}
    conflicts = set(x.columns) & set(y_carry)
    x_names = {c: (c + suffix[0] if c in conflicts and (keep_keys or c not in x_equal) else c)
               for c in x.columns}
    y_names = {c: (c + suffix[1] if c in conflicts else c) for c in y_carry}

    xd = x.rename(x_names).with_row_index(_XR)
    fused = [(x_names[c.left], f"__polyr_fused_{i}") for i, c in enumerate(conds)
             if c.op == "==" and not keep_keys]
    yd = y.select([pl.col(c).alias(y_names[c]) for c in y_carry]
                  + [pl.col(c.right).alias(tmp)
                     for (_, tmp), c in zip(fused, equalities)]).with_row_index(_YR)

    # --- controles previos: relationship, multiple, unmatched -------------------
    matches = _match_pairs(x, y, conds, nulls_equal)
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
    # dplyr solo avisa de muchos-a-muchos en uniones por igualdad: en una por
    # desigualdad esa relación es lo normal.
    solo_igualdades = len(equalities) == len(conds)
    if (relationship is None and solo_igualdades and multiple == "all"
            and x_multi is not None and y_multi is not None):
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

    # --- armado de la salida ---------------------------------------------------
    rows = _row_pairs(matches, xd.select(_XR), yd.select(_YR), how)
    if multiple != "all":
        pick = pl.col(_YR).max() if multiple == "last" else pl.col(_YR).min()
        rows = rows.filter(pl.col(_XR).is_null() | pl.col(_YR).is_null()
                           | (pl.col(_YR) == pick.over(_XR)))

    joined = (rows.join(xd, on=_XR, how="left", maintain_order="left")
              .join(yd, on=_YR, how="left", maintain_order="left"))
    # En las filas que solo existen en `y`, la clave fundida la aporta `y`.
    if fused:
        joined = joined.with_columns([pl.coalesce([pl.col(name), pl.col(tmp)]).alias(name)
                                      for name, tmp in fused])
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
    conds = _keys(x, y, by, verb_name)
    xc, yc = _cast_keys(x, y, conds, verb_name)
    matched = _match_pairs(xc, yc, conds, nulls_equal).get_column(_XR).unique()
    if anti:
        todas = pl.int_range(0, x.height, dtype=matched.dtype, eager=True)
        rows = todas.filter(~todas.is_in(matched))
    else:
        rows = matched.sort()
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
    conds = _keys(xf, yf, by, "nest_join")
    xc, yc = _cast_keys(xf, yf, conds, "nest_join")
    merged = [] if keep is True else [c.right for c in conds if c.op == "=="]
    nested = [c for c in yc.columns if c not in merged]

    cell = pl.struct([pl.col(c) for c in nested]) if nested else pl.struct(pl.lit(0).alias("_"))
    matches = _match_pairs(xc, yc, conds, nulls_equal)
    celdas = (matches.join(yc.with_row_index(_YR).select(_YR, cell.alias(name)),
                           on=_YR, how="left", maintain_order="left")
              .group_by(_XR, maintain_order=True).agg(pl.col(name)))
    out = xc.with_row_index(_XR).join(celdas, on=_XR, how="left", maintain_order="left")
    # Sin parejas, dplyr deja una tabla de 0 filas, no un faltante.
    vacia = pl.lit([], dtype=celdas.schema[name])
    return rewrap(out.with_columns(pl.col(name).fill_null(vacia)).drop(_XR), groups)
