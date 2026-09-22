import polars as pl
import pytest

from polyr import arrange, desc, f
from polyr.errors import DplyrError


def test_ascendente():
    df = pl.DataFrame({"x": [3, 1, 2]})
    assert arrange(df, f.x)["x"].to_list() == [1, 2, 3]


def test_desc():
    df = pl.DataFrame({"x": [3, 1, 2]})
    assert (df >> arrange(desc(f.x)))["x"].to_list() == [3, 2, 1]


def test_na_y_nan_siempre_al_final():
    nan = float("nan")
    df = pl.DataFrame({"x": [2.0, None, nan, 1.0]})
    asc = arrange(df, f.x)["x"].to_list()
    des = arrange(df, desc(f.x))["x"].to_list()
    assert asc[:2] == [1.0, 2.0]
    assert des[:2] == [2.0, 1.0]  # polars pondría NaN primero en orden descendente


def test_es_estable():
    df = pl.DataFrame({"k": [1, 0, 1, 0], "orden": [0, 1, 2, 3]})
    assert arrange(df, f.k)["orden"].to_list() == [1, 3, 0, 2]


def test_varias_claves():
    df = pl.DataFrame({"a": [1, 1, 2, 2], "b": [1, 2, 1, 2]})
    out = arrange(df, desc(f.a), f.b)
    assert list(zip(out["a"], out["b"])) == [(2, 1), (2, 2), (1, 1), (1, 2)]


def test_clave_calculada():
    df = pl.DataFrame({"a": [1, 5, 3], "b": [4, 0, 1]})
    assert arrange(df, f.a - f.b)["a"].to_list() == [1, 3, 5]


def test_texto_en_locale_c():
    df = pl.DataFrame({"s": ["b", "B", "a", "A"]})
    assert arrange(df, f.s)["s"].to_list() == ["A", "B", "a", "b"]


def test_desc_de_texto():
    df = pl.DataFrame({"s": ["b", "a", "c"]})
    assert arrange(df, desc(f.s))["s"].to_list() == ["c", "b", "a"]


def test_sin_claves_no_cambia_nada():
    df = pl.DataFrame({"x": [2, 1]})
    assert arrange(df)["x"].to_list() == [2, 1]


def test_columna_inexistente():
    with pytest.raises(DplyrError, match="`z`"):
        arrange(pl.DataFrame({"x": [1]}), f.z)


def test_argumento_con_nombre():
    with pytest.raises(DplyrError, match="nombre"):
        arrange(pl.DataFrame({"x": [1]}), x=f.x)
