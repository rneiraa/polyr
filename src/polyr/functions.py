"""Funciones vectoriales con la semántica de R/dplyr, no la de polars.

Cada función devuelve un nodo :class:`~polyr.expr.Expr`; nada se calcula hasta
que un verbo compila la expresión. Al compilar se consultan los tipos para
aplicar las reglas de vctrs.
"""
from __future__ import annotations

from typing import Any

import polars as pl

from ._types import kind, ptype_common, type_name
from .errors import ExprError
from .expr import Call, EvalContext, Expr, wrap

_NUMERIC = ("logical", "integer", "double", "unspecified")

__all__ = [
    # resúmenes
    "mean", "sum", "min", "max", "median", "sd", "var", "first", "last", "n_distinct", "n",
    # condicionales y faltantes
    "is_na", "if_else", "case_when", "coalesce", "na_if", "between", "near",
    # ventana
    "lag", "lead", "row_number", "min_rank", "dense_rank", "percent_rank", "cume_dist",
    "ntile", "cumsum", "cummean", "cummin", "cummax", "cumall", "cumany",
    # orden
    "desc",
]


def _missing(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
    """Detección de faltantes de vctrs: en dobles, NaN también cuenta."""
    if ctx.dtype(e).is_float():
        return e.is_null() | e.is_nan()
    return e.is_null()


def mean(x: Any, na_rm: bool = False) -> Call:
    """Media aritmética, como ``mean()`` de R.

    * Con algún NA (o NaN) y ``na_rm=False`` el resultado es NA (polars, en
      cambio, ignora los nulos en silencio).
    * ``na_rm=True`` descarta NA **y** NaN, como en R.
    * Acepta lógicos (TRUE cuenta como 1).
    """
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        dtype = ctx.dtype(e)
        if kind(dtype) not in ("logical", "integer", "double", "unspecified"):
            raise ExprError(f"`mean()` necesita un vector numérico o lógico, no {type_name(dtype)}.")
        e = e.cast(pl.Float64)
        if na_rm:
            return e.fill_nan(None).mean()
        return pl.when(e.is_null().any()).then(None).otherwise(e.mean())

    return Call("mean", compile_, [wrap(x)], "na_rm=True" if na_rm else "")


def is_na(x: Any) -> Call:
    """TRUE donde hay un valor faltante. Como en R, ``is_na(NaN)`` es TRUE."""
    return Call("is_na", _missing, [wrap(x)])


def if_else(condition: Any, true: Any, false: Any, missing: Any = None) -> Call:
    """Condicional vectorizado y estricto con los tipos, como ``dplyr::if_else()``.

    * ``condition`` debe ser lógico.
    * ``true``, ``false`` y ``missing`` se llevan a su tipo común; si no lo
      tienen (p. ej. ``<double>`` y ``<character>``) es un error.
    * Donde ``condition`` es NA el resultado es ``missing`` (NA por defecto),
      **no** ``false``.
    """
    args = [wrap(condition), wrap(true), wrap(false), wrap(missing)]

    def compile_(ctx: EvalContext, cond: pl.Expr, t: pl.Expr, fl: pl.Expr, m: pl.Expr) -> pl.Expr:
        cdtype = ctx.dtype(cond)
        if kind(cdtype) not in ("logical", "unspecified"):
            raise ExprError(f"`condition` debe ser un vector lógico, no {type_name(cdtype)}.")
        common = ptype_common([("true", ctx.dtype(t)), ("false", ctx.dtype(fl)),
                               ("missing", ctx.dtype(m))])
        t, fl, m = t.cast(common), fl.cast(common), m.cast(common)
        cond = cond.cast(pl.Boolean)
        return pl.when(cond.is_null()).then(m).when(cond).then(t).otherwise(fl)

    extra = "" if missing is None else f"missing={args[3]!r}"
    return Call("if_else", compile_, args[:3] + [args[3]], extra)


def coalesce(*values: Any) -> Call:
    """Primer valor no faltante de cada posición, como ``dplyr::coalesce()``.

    Todos los argumentos se llevan a su tipo común; NaN cuenta como faltante.
    """
    if not values:
        raise ExprError("`coalesce()` necesita al menos un argumento.")
    args = [wrap(v) for v in values]

    def compile_(ctx: EvalContext, *es: pl.Expr) -> pl.Expr:
        common = ptype_common((f"..{i}", ctx.dtype(e)) for i, e in enumerate(es, 1))
        prepared = []
        for e in es:
            e = e.cast(common)
            prepared.append(e.fill_nan(None) if common.is_float() else e)
        return pl.coalesce(prepared)

    return Call("coalesce", compile_, args)


def n() -> Call:
    """Número de filas del grupo actual (sin grupos: de la tabla)."""
    return Call("n", lambda ctx: pl.len().cast(pl.Int64), [])


class Desc(Expr):
    """Orden descendente. En ``arrange()`` marca la clave; fuera de él, niega."""

    def __init__(self, inner: Expr):
        self.inner = inner

    def to_polars(self, ctx: EvalContext) -> pl.Expr:
        e = self.inner.to_polars(ctx)
        dtype = ctx.dtype(e)
        if kind(dtype) not in ("logical", "integer", "double"):
            raise ExprError(
                f"Fuera de `arrange()`, `desc()` solo admite vectores numéricos, no {type_name(dtype)}."
            )
        return -(e.cast(pl.Int64) if dtype == pl.Boolean else e)

    def columns(self) -> set[str]:
        return self.inner.columns()

    def __repr__(self) -> str:
        return f"desc({self.inner!r})"


def desc(x: Any) -> Desc:
    """Ordena en forma descendente dentro de ``arrange()``."""
    return Desc(wrap(x))


# =============================================================================
# Resúmenes
# =============================================================================

def _numeric_arg(ctx: EvalContext, e: pl.Expr, fname: str, allow_other: bool = False) -> pl.DataType:
    dtype = ctx.dtype(e)
    if not allow_other and kind(dtype) not in _NUMERIC:
        raise ExprError(f"`{fname}()` necesita un vector numérico o lógico, no {type_name(dtype)}.")
    return dtype


def _na_guard(ctx: EvalContext, e: pl.Expr, result: pl.Expr) -> pl.Expr:
    """NA si hay algún faltante (NA o NaN), como en R sin ``na.rm``."""
    return pl.when(_missing(ctx, e).any()).then(None).otherwise(result)


def _drop_missing(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
    return e.fill_nan(None).drop_nulls() if ctx.dtype(e).is_float() else e.drop_nulls()


def sum(x: Any, na_rm: bool = False) -> Call:  # noqa: A001 - mismo nombre que en R
    """Suma. Con NA y ``na_rm=False`` es NA; la suma vacía es 0.

    Los lógicos cuentan TRUE como 1; enteros suman a entero.
    """
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        dtype = _numeric_arg(ctx, e, "sum")
        if dtype == pl.Boolean or dtype == pl.Null:
            e = e.cast(pl.Int64)
        elif dtype.is_integer():
            e = e.cast(pl.Int64)
        if na_rm:
            return e.fill_nan(None).sum() if dtype.is_float() else e.sum()
        # En R, NaN se propaga en la suma (no es NA): sum(c(1, NaN)) es NaN.
        return pl.when(e.is_null().any()).then(None).otherwise(e.sum())

    return Call("sum", compile_, [wrap(x)], "na_rm=True" if na_rm else "")


def _extreme(fname: str, x: Any, na_rm: bool) -> Call:
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        dtype = ctx.dtype(e)
        if kind(dtype) not in _NUMERIC + ("character", "date", "datetime", "duration"):
            raise ExprError(f"`{fname}()` no admite {type_name(dtype)}.")
        if dtype == pl.Boolean:
            e = e.cast(pl.Int64)
        if na_rm:
            e = e.fill_nan(None) if dtype.is_float() else e
            return e.min() if fname == "min" else e.max()
        if dtype.is_float():  # NaN se propaga, como en R
            result = e.nan_min() if fname == "min" else e.nan_max()
        else:
            result = e.min() if fname == "min" else e.max()
        return pl.when(e.is_null().any()).then(None).otherwise(result)

    return Call(fname, compile_, [wrap(x)], "na_rm=True" if na_rm else "")


def min(x: Any, na_rm: bool = False) -> Call:  # noqa: A001
    """Mínimo. Con NA y ``na_rm=False`` es NA; NaN se propaga.

    A diferencia de R (que devuelve ``Inf`` con una advertencia), el mínimo de
    un vector vacío es NA.
    """
    return _extreme("min", x, na_rm)


def max(x: Any, na_rm: bool = False) -> Call:  # noqa: A001
    """Máximo. Mismas reglas que :func:`min`."""
    return _extreme("max", x, na_rm)


def median(x: Any, na_rm: bool = False) -> Call:
    """Mediana. Con algún NA o NaN y ``na_rm=False`` es NA."""
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        _numeric_arg(ctx, e, "median")
        if na_rm:
            return _drop_missing(ctx, e).cast(pl.Float64).median()
        return _na_guard(ctx, e, e.cast(pl.Float64).median())

    return Call("median", compile_, [wrap(x)], "na_rm=True" if na_rm else "")


def _dispersion(fname: str, x: Any, na_rm: bool) -> Call:
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        _numeric_arg(ctx, e, fname)
        values = _drop_missing(ctx, e) if na_rm else e
        values = values.cast(pl.Float64)
        stat = values.std(ddof=1) if fname == "sd" else values.var(ddof=1)
        stat = pl.when(values.count() < 2).then(None).otherwise(stat)
        return stat if na_rm else _na_guard(ctx, e, stat)

    return Call(fname, compile_, [wrap(x)], "na_rm=True" if na_rm else "")


def sd(x: Any, na_rm: bool = False) -> Call:
    """Desviación estándar muestral (denominador n - 1). NA con menos de 2 valores."""
    return _dispersion("sd", x, na_rm)


def var(x: Any, na_rm: bool = False) -> Call:
    """Varianza muestral (denominador n - 1). NA con menos de 2 valores."""
    return _dispersion("var", x, na_rm)


def _first_last(fname: str, x: Any, default: Any, na_rm: bool) -> Call:
    args = [wrap(x), wrap(default)]

    def compile_(ctx: EvalContext, e: pl.Expr, d: pl.Expr) -> pl.Expr:
        common = ptype_common([("x", ctx.dtype(e)), ("default", ctx.dtype(d))])
        e, d = e.cast(common), d.cast(common)
        values = _drop_missing(ctx, e) if na_rm else e
        picked = values.first() if fname == "first" else values.last()
        return pl.when(values.len() == 0).then(d.first()).otherwise(picked)

    extra = ", ".join(p for p in (f"default={args[1]!r}" if default is not None else "",
                                  "na_rm=True" if na_rm else "") if p)
    return Call(fname, compile_, args, extra)


def first(x: Any, default: Any = None, na_rm: bool = False) -> Call:
    """Primer valor (``default`` si no hay ninguno)."""
    return _first_last("first", x, default, na_rm)


def last(x: Any, default: Any = None, na_rm: bool = False) -> Call:
    """Último valor (``default`` si no hay ninguno)."""
    return _first_last("last", x, default, na_rm)


def n_distinct(*xs: Any, na_rm: bool = False) -> Call:
    """Número de valores (o combinaciones) distintos. NA cuenta como un valor,
    salvo con ``na_rm=True``."""
    if not xs:
        raise ExprError("`n_distinct()` necesita al menos un argumento.")
    args = [wrap(x) for x in xs]

    def compile_(ctx: EvalContext, *es: pl.Expr) -> pl.Expr:
        prepared = [e.fill_nan(None) if ctx.dtype(e).is_float() else e for e in es]
        if len(prepared) == 1:
            values = prepared[0]
            return (values.drop_nulls() if na_rm else values).n_unique().cast(pl.Int64)
        combo = pl.struct([p.alias(f"_{i}") for i, p in enumerate(prepared)])
        if na_rm:
            complete = pl.all_horizontal([p.is_not_null() for p in prepared])
            combo = combo.filter(complete)
        return combo.n_unique().cast(pl.Int64)

    return Call("n_distinct", compile_, args, "na_rm=True" if na_rm else "")


# =============================================================================
# Condicionales y faltantes
# =============================================================================

def case_when(*cases: tuple[Any, Any], _default: Any = None) -> Call:
    """Condicional múltiple, como ``dplyr::case_when()``.

    ``case_when((f.x < 0, "negativo"), (f.x == 0, "cero"), _default="positivo")``

    * Las condiciones se evalúan en orden; gana la primera TRUE.
    * Una condición NA cuenta como FALSE (igual que en dplyr).
    * Todos los valores y ``_default`` se llevan a su tipo común.
    """
    if not cases:
        raise ExprError("`case_when()` necesita al menos un caso (condición, valor).")
    flat: list[Expr] = []
    for i, case in enumerate(cases, 1):
        if not isinstance(case, tuple) or len(case) != 2:
            raise TypeError(f"El caso {i} de `case_when()` debe ser una tupla (condición, valor).")
        flat += [wrap(case[0]), wrap(case[1])]
    flat.append(wrap(_default))

    def compile_(ctx: EvalContext, *es: pl.Expr) -> pl.Expr:
        conds, values, default = list(es[0:-1:2]), list(es[1:-1:2]), es[-1]
        for i, c in enumerate(conds, 1):
            dtype = ctx.dtype(c)
            if kind(dtype) not in ("logical", "unspecified"):
                raise ExprError(f"La condición del caso {i} debe ser un vector lógico, "
                                f"no {type_name(dtype)}.")
        common = ptype_common([(f"caso {i}", ctx.dtype(v)) for i, v in enumerate(values, 1)]
                              + [("_default", ctx.dtype(default))])
        chain = pl.when(conds[0].cast(pl.Boolean).fill_null(False)).then(values[0].cast(common))
        for c, v in zip(conds[1:], values[1:]):
            chain = chain.when(c.cast(pl.Boolean).fill_null(False)).then(v.cast(common))
        return chain.otherwise(default.cast(common))

    return Call("case_when", compile_, flat)


def na_if(x: Any, y: Any) -> Call:
    """Convierte en NA los valores de ``x`` iguales a ``y``. Conserva el tipo de ``x``."""
    def compile_(ctx: EvalContext, e: pl.Expr, v: pl.Expr) -> pl.Expr:
        xt, yt = ctx.dtype(e), ctx.dtype(v)
        common = ptype_common([("x", xt), ("y", yt)])
        if kind(common) != kind(xt) and kind(yt) != "unspecified":
            raise ExprError(f"No se puede convertir `y` {type_name(yt)} a {type_name(xt)}.")
        return pl.when(e.cast(common) == v.cast(common)).then(None).otherwise(e)

    return Call("na_if", compile_, [wrap(x), wrap(y)])


def between(x: Any, left: Any, right: Any) -> Call:
    """``left <= x <= right`` (inclusivo). NA si alguno es NA."""
    return Call("between", lambda ctx, e, lo, hi: (e >= lo) & (e <= hi),
                [wrap(x), wrap(left), wrap(right)])


def near(x: Any, y: Any, tol: float = 1.4901161193847656e-08) -> Call:
    """Igualdad con tolerancia para dobles (por defecto ``sqrt(eps)``, como R)."""
    return Call("near", lambda ctx, a, b: (a - b).abs() < tol, [wrap(x), wrap(y)])


# =============================================================================
# Funciones de ventana
# =============================================================================

def _shift(fname: str, x: Any, n: int, default: Any) -> Call:
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ExprError(f"`n` en `{fname}()` debe ser un entero no negativo.")

    def compile_(ctx: EvalContext, e: pl.Expr, d: pl.Expr) -> pl.Expr:
        common = ptype_common([("x", ctx.dtype(e)), ("default", ctx.dtype(d))])
        e = e.cast(common)
        shifted = e.shift(n if fname == "lag" else -n)
        if default is None:
            return shifted
        pos = pl.int_range(pl.len())
        edge = pos < n if fname == "lag" else pos >= pl.len() - n
        return pl.when(edge).then(d.cast(common)).otherwise(shifted)

    extra = "" if n == 1 else f"n={n}"
    return Call(fname, compile_, [wrap(x), wrap(default)], extra)


def lag(x: Any, n: int = 1, default: Any = None) -> Call:
    """Valor ``n`` filas antes (``default`` al principio, NA por defecto)."""
    return _shift("lag", x, n, default)


def lead(x: Any, n: int = 1, default: Any = None) -> Call:
    """Valor ``n`` filas después (``default`` al final, NA por defecto)."""
    return _shift("lead", x, n, default)


def _prep_rank(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
    return e.fill_nan(None) if ctx.dtype(e).is_float() else e


def _rank(fname: str, method: str, x: Any) -> Call:
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        return _prep_rank(ctx, e).rank(method).cast(pl.Int64)
    return Call(fname, compile_, [wrap(x)])


def row_number(x: Any = None) -> Call:
    """Sin argumentos: 1, 2, ..., n. Con ``x``: ranking con empates por orden de aparición.

    Como en dplyr, los rankings empiezan en 1 y NA queda NA.
    """
    if x is None:
        return Call("row_number", lambda ctx: pl.int_range(1, pl.len() + 1, dtype=pl.Int64), [])
    return _rank("row_number", "ordinal", x)


def min_rank(x: Any) -> Call:
    """Ranking con huecos (empates reciben el menor rango): 1, 1, 3."""
    return _rank("min_rank", "min", x)


def dense_rank(x: Any) -> Call:
    """Ranking sin huecos: 1, 1, 2."""
    return _rank("dense_rank", "dense", x)


def percent_rank(x: Any) -> Call:
    """``(min_rank - 1) / (n - 1)``, con n = número de valores no NA."""
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        e = _prep_rank(ctx, e)
        r = e.rank("min").cast(pl.Float64)
        return (r - 1) / (e.count().cast(pl.Float64) - 1)
    return Call("percent_rank", compile_, [wrap(x)])


def cume_dist(x: Any) -> Call:
    """Proporción de valores menores o iguales: ``max_rank / n``."""
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        e = _prep_rank(ctx, e)
        return e.rank("max").cast(pl.Float64) / e.count().cast(pl.Float64)
    return Call("cume_dist", compile_, [wrap(x)])


def ntile(x: Any, n: int) -> Call:
    """Divide en ``n`` grupos lo más parejos posible (los primeros, más grandes).

    Reproduce el algoritmo de dplyr 1.1.
    """
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise ExprError("`n` en `ntile()` debe ser un entero positivo.")

    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        e = _prep_rank(ctx, e)
        r = e.rank("ordinal").cast(pl.Int64)
        size = e.count().cast(pl.Int64)
        n_larger = size % n
        larger = (size + n - 1) // n        # ceiling(size / n)
        smaller = size // n                 # floor(size / n)
        threshold = larger * n_larger
        in_larger = r <= threshold
        bins_larger = (r + larger - 1) // larger
        bins_smaller = (r - threshold + smaller - 1) // pl.when(smaller == 0).then(1).otherwise(smaller) + n_larger
        return pl.when(in_larger).then(bins_larger).otherwise(bins_smaller).cast(pl.Int64)

    return Call("ntile", compile_, [wrap(x)], f"n={n}")


def _cumulative(fname: str, x: Any) -> Call:
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        dtype = _numeric_arg(ctx, e, fname)
        if dtype == pl.Boolean:
            e = e.cast(pl.Int64)
        missing_seen = e.is_null().cast(pl.Int64).cum_sum() > 0
        if fname == "cumsum":
            result = e.cum_sum()
        elif fname == "cummin":
            result = e.cum_min()
        elif fname == "cummax":
            result = e.cum_max()
        else:  # cummean
            result = e.cast(pl.Float64).cum_sum() / pl.int_range(1, pl.len() + 1)
        # En R, un NA contamina todos los valores acumulados posteriores.
        return pl.when(missing_seen).then(None).otherwise(result)
    return Call(fname, compile_, [wrap(x)])


def cumsum(x: Any) -> Call:
    """Suma acumulada; desde el primer NA, todo es NA (como en R)."""
    return _cumulative("cumsum", x)


def cummean(x: Any) -> Call:
    """Media acumulada; desde el primer NA, todo es NA."""
    return _cumulative("cummean", x)


def cummin(x: Any) -> Call:
    """Mínimo acumulado; desde el primer NA, todo es NA."""
    return _cumulative("cummin", x)


def cummax(x: Any) -> Call:
    """Máximo acumulado; desde el primer NA, todo es NA."""
    return _cumulative("cummax", x)


def _cum_logical(fname: str, x: Any) -> Call:
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        dtype = ctx.dtype(e)
        if kind(dtype) not in ("logical", "unspecified"):
            raise ExprError(f"`{fname}()` necesita un vector lógico, no {type_name(dtype)}.")
        e = e.cast(pl.Boolean)
        decisive = (e == (fname == "cumany")).fill_null(False).cast(pl.Int64).cum_sum() > 0
        na_seen = e.is_null().cast(pl.Int64).cum_sum() > 0
        return (pl.when(decisive).then(pl.lit(fname == "cumany"))
                .when(na_seen).then(None)
                .otherwise(pl.lit(fname != "cumany")))
    return Call(fname, compile_, [wrap(x)])


def cumall(x: Any) -> Call:
    """TRUE mientras todos los valores hasta aquí sean TRUE (una vez FALSE, siempre FALSE)."""
    return _cum_logical("cumall", x)


def cumany(x: Any) -> Call:
    """TRUE desde el primer TRUE en adelante."""
    return _cum_logical("cumany", x)
