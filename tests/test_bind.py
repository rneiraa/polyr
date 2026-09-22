import polars as pl
import pytest

from polyr import DplyrMessage, bind_cols, bind_rows, f, group_by, group_vars
from polyr.errors import DplyrError


def test_bind_rows_por_nombre_y_rellena_na():
    a = pl.DataFrame({"x": [1], "y": ["a"]})
    b = pl.DataFrame({"y": ["b"], "z": [True]})
    out = bind_rows(a, b)
    assert out.columns == ["x", "y", "z"]
    assert out["x"].to_list() == [1, None]
    assert out["z"].to_list() == [None, True]


def test_bind_rows_tipo_comun():
    out = bind_rows(pl.DataFrame({"x": [1]}), pl.DataFrame({"x": [2.5]}))
    assert out["x"].dtype == pl.Float64


def test_bind_rows_tipos_incompatibles():
    with pytest.raises(DplyrError, match="No se puede combinar"):
        bind_rows(pl.DataFrame({"x": [1]}), pl.DataFrame({"x": ["a"]}))


def test_bind_rows_id():
    a, b = pl.DataFrame({"x": [1]}), pl.DataFrame({"x": [2]})
    assert bind_rows(a, b, _id="origen")["origen"].to_list() == ["1", "2"]
    assert bind_rows({"a": a, "b": b}, _id="origen")["origen"].to_list() == ["a", "b"]


def test_bind_rows_lista_y_grupos():
    a = pl.DataFrame({"g": [1], "x": [1]})
    out = bind_rows([group_by(a, f.g), a])
    assert group_vars(out) == ["g"]
    assert out.height == 2


def test_bind_cols():
    out = bind_cols(pl.DataFrame({"a": [1, 2]}), pl.DataFrame({"b": [3, 4]}))
    assert out.columns == ["a", "b"]


def test_bind_cols_recicla_tamano_1():
    out = bind_cols(pl.DataFrame({"a": [1, 2]}), pl.DataFrame({"b": [0]}))
    assert out["b"].to_list() == [0, 0]


def test_bind_cols_repara_nombres():
    with pytest.warns(DplyrMessage, match=r"`a` -> `a...1`"):
        out = bind_cols(pl.DataFrame({"a": [1]}), pl.DataFrame({"a": [2]}))
    assert out.columns == ["a...1", "a...2"]


def test_bind_cols_tamanos_distintos():
    with pytest.raises(DplyrError, match="mismo número de filas"):
        bind_cols(pl.DataFrame({"a": [1, 2]}), pl.DataFrame({"b": [1, 2, 3]}))
