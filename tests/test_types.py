"""Reglas de vctrs: tipo común, conversión sin pérdida y reciclado."""
import polars as pl
import pytest

from polyr._types import cast, kind, ptype_common, recycle, type_name
from polyr.errors import ExprError


@pytest.mark.parametrize("dtype, expected", [
    (pl.Boolean, "logical"), (pl.Int32, "integer"), (pl.UInt8, "integer"),
    (pl.Float64, "double"), (pl.String, "character"), (pl.Null, "unspecified"),
    (pl.Date, "date"), (pl.Datetime("us"), "datetime"), (pl.List(pl.Int64), "list"),
])
def test_nombres_de_tipos_de_r(dtype, expected):
    assert kind(dtype) == expected


def test_type_name():
    assert type_name(pl.Float64) == "<double>"


@pytest.mark.parametrize("a, b, expected", [
    (pl.Boolean, pl.Int64, pl.Int64),
    (pl.Int64, pl.Float64, pl.Float64),
    (pl.Boolean, pl.Float64, pl.Float64),
    (pl.Int32, pl.Int64, pl.Int64),
    (pl.Int8, pl.UInt8, pl.Int64),
    (pl.Float32, pl.Float64, pl.Float64),
    (pl.String, pl.String, pl.String),
    (pl.Null, pl.String, pl.String),
    (pl.Int64, pl.Null, pl.Int64),
    (pl.Null, pl.Null, pl.Null),
])
def test_tipo_comun(a, b, expected):
    assert ptype_common([("a", a), ("b", b)]) == expected


def test_tipo_comun_es_simetrico():
    assert ptype_common([("a", pl.Int64), ("b", pl.Boolean)]) == pl.Int64


@pytest.mark.parametrize("a, b", [(pl.Float64, pl.String), (pl.Boolean, pl.String),
                                  (pl.Date, pl.Int64)])
def test_tipos_incompatibles(a, b):
    with pytest.raises(ExprError, match=r"No se puede combinar `a` <.+> con `b` <.+>"):
        ptype_common([("a", a), ("b", b)])


def test_cast_hacia_arriba():
    assert cast(pl.Series([1, 2]), pl.Float64).to_list() == [1.0, 2.0]
    assert cast(pl.Series([True, None]), pl.Int64).to_list() == [1, None]


def test_cast_hacia_abajo_sin_perdida():
    assert cast(pl.Series([1.0, None, 3.0]), pl.Int64).to_list() == [1, None, 3]
    assert cast(pl.Series([0, 1]), pl.Boolean).to_list() == [False, True]


@pytest.mark.parametrize("values, to", [
    ([1.0, 2.5], pl.Int64),
    ([1.0, float("nan")], pl.Int64),
    ([1.0, float("inf")], pl.Int64),
    ([0, 2], pl.Boolean),
])
def test_cast_con_perdida_es_error(values, to):
    with pytest.raises(ExprError, match="sin perder precisión"):
        cast(pl.Series(values), to)


def test_cast_indica_los_indices():
    with pytest.raises(ExprError, match=r"Índices \(base 0\): 1, 3"):
        cast(pl.Series([1.0, 1.5, 2.0, 2.5]), pl.Int64)


def test_cast_entre_familias_es_error():
    with pytest.raises(ExprError, match="No se puede convertir"):
        cast(pl.Series([1, 2]), pl.String)


def test_cast_desde_na_sin_tipo():
    assert cast(pl.Series([None, None]), pl.String).dtype == pl.String


def test_reciclado():
    assert recycle(pl.Series([7]), 3, "x").to_list() == [7, 7, 7]
    assert recycle(pl.Series([1, 2, 3]), 3, "x").to_list() == [1, 2, 3]
    with pytest.raises(ExprError, match="tamaño 3 o 1, no 2"):
        recycle(pl.Series([1, 2]), 3, "`x`")
