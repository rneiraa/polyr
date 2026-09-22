"""Funciones de base R de uso diario dentro de ``mutate()`` y ``filter()``.

No son parte de dplyr, pero cualquier análisis las necesita, y sus reglas
(NA, redondeo, conversiones) deben ser las de R.
"""
from __future__ import annotations

import math as _math
from typing import Any, Iterable

import polars as pl

from ._types import kind, ptype_common, type_name
from .errors import ExprError
from .expr import Call, EvalContext, Values, wrap

__all__ = ["is_in", "abs", "sqrt", "exp", "log", "log2", "log10", "floor", "ceiling",
           "round", "pmin", "pmax", "as_integer", "as_double", "as_character", "as_logical"]

_NUMERIC = ("logical", "integer", "double", "unspecified")


def _numeric(ctx: EvalContext, e: pl.Expr, fname: str) -> pl.Expr:
    dtype = ctx.dtype(e)
    if kind(dtype) not in _NUMERIC:
        raise ExprError(f"`{fname}()` necesita un vector numérico, no {type_name(dtype)}.")
    return e.cast(pl.Int64) if dtype in (pl.Boolean, pl.Null) else e


def is_in(x: Any, values: Iterable[Any]) -> Call:
    """``x %in% values``. **Nunca devuelve NA**: ``NA %in% c(1, NA)`` es TRUE y
    ``NA %in% c(1)`` es FALSE, como en R (polars devolvería nulo)."""
    vals = values if isinstance(values, pl.Series) else pl.Series(list(values))

    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        common = ptype_common([("x", ctx.dtype(e)), ("values", vals.dtype)])
        target = vals.cast(common)
        has_na = target.null_count() > 0
        return (pl.when(e.is_null()).then(pl.lit(has_na))
                .otherwise(e.cast(common).is_in(target.drop_nulls().implode())))

    return Call("is_in", compile_, [wrap(x)], repr(Values(vals)))


def _unary(fname: str, fn, doc: str):
    def factory(x: Any) -> Call:
        def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
            return fn(_numeric(ctx, e, fname))
        return Call(fname, compile_, [wrap(x)])
    factory.__name__ = factory.__qualname__ = fname
    factory.__doc__ = doc
    return factory


abs = _unary("abs", lambda e: e.abs(), "Valor absoluto.")  # noqa: A001
sqrt = _unary("sqrt", lambda e: e.cast(pl.Float64).sqrt(), "Raíz cuadrada (NaN para negativos, como R).")
exp = _unary("exp", lambda e: e.cast(pl.Float64).exp(), "Exponencial.")
log2 = _unary("log2", lambda e: e.cast(pl.Float64).log(2), "Logaritmo en base 2.")
log10 = _unary("log10", lambda e: e.cast(pl.Float64).log10(), "Logaritmo en base 10.")
floor = _unary("floor", lambda e: e.cast(pl.Float64).floor(), "Redondeo hacia abajo (devuelve double, como R).")
ceiling = _unary("ceiling", lambda e: e.cast(pl.Float64).ceil(), "Redondeo hacia arriba (devuelve double).")


def log(x: Any, base: float = _math.e) -> Call:
    """Logaritmo (natural por defecto). ``log(0)`` es ``-Inf``; negativos dan NaN."""
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        return _numeric(ctx, e, "log").cast(pl.Float64).log(base)
    return Call("log", compile_, [wrap(x)], "" if base == _math.e else f"base={base}")


def round(x: Any, digits: int = 0) -> Call:  # noqa: A001
    """Redondeo con la regla de R (IEC 60559, "mitad al par"): ``round(2.5)`` es 2."""
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        e = _numeric(ctx, e, "round")
        if ctx.dtype(e).is_integer() and digits >= 0:
            return e
        return e.cast(pl.Float64).round(digits, mode="half_to_even")
    return Call("round", compile_, [wrap(x)], "" if digits == 0 else f"digits={digits}")


def _parallel(fname: str, xs: tuple, na_rm: bool) -> Call:
    if not xs:
        raise ExprError(f"`{fname}()` necesita al menos un argumento.")

    def compile_(ctx: EvalContext, *es: pl.Expr) -> pl.Expr:
        common = ptype_common((f"..{i}", ctx.dtype(e)) for i, e in enumerate(es, 1))
        es = tuple(e.cast(common) for e in es)
        result = pl.min_horizontal(es) if fname == "pmin" else pl.max_horizontal(es)
        if na_rm:
            return result
        any_na = pl.any_horizontal([e.is_null() for e in es])
        return pl.when(any_na).then(None).otherwise(result)

    return Call(fname, compile_, [wrap(x) for x in xs], "na_rm=True" if na_rm else "")


def pmin(*xs: Any, na_rm: bool = False) -> Call:
    """Mínimo elemento a elemento. NA si alguno es NA, salvo ``na_rm=True``."""
    return _parallel("pmin", xs, na_rm)


def pmax(*xs: Any, na_rm: bool = False) -> Call:
    """Máximo elemento a elemento. NA si alguno es NA, salvo ``na_rm=True``."""
    return _parallel("pmax", xs, na_rm)


def _as(fname: str, target: pl.DataType, doc: str):
    def factory(x: Any) -> Call:
        def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
            src = ctx.dtype(e)
            if target == pl.Int64 and src.is_float():
                return e.cast(pl.Int64, strict=False)  # trunca hacia cero, como R
            if target == pl.Int64 and kind(src) == "character":
                return e.cast(pl.Float64, strict=False).cast(pl.Int64, strict=False)
            if target == pl.Boolean and kind(src) == "character":
                upper = e.str.to_uppercase()
                return (pl.when(upper.is_in(["TRUE", "T"])).then(True)
                        .when(upper.is_in(["FALSE", "F"])).then(False).otherwise(None))
            if target == pl.String and src == pl.Boolean:
                return pl.when(e).then(pl.lit("TRUE")).when(~e).then(pl.lit("FALSE")).otherwise(None)
            return e.cast(target, strict=False)
        return Call(fname, compile_, [wrap(x)])
    factory.__name__ = factory.__qualname__ = fname
    factory.__doc__ = doc
    return factory


as_integer = _as("as_integer", pl.Int64,
                 "Convierte a entero. Los dobles se truncan hacia cero; lo no convertible es NA.")
as_double = _as("as_double", pl.Float64, "Convierte a double; lo no convertible es NA.")
as_character = _as("as_character", pl.String,
                   "Convierte a texto. Los lógicos se escriben TRUE/FALSE, como en R.")
as_logical = _as("as_logical", pl.Boolean,
                 'Convierte a lógico. Acepta "TRUE"/"T"/"FALSE"/"F" (sin importar mayúsculas).')
