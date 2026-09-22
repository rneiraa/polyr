import polars as pl
import pytest

from polyr import (DplyrMessage, add_count, count, distinct, f, group_by, group_vars, tally)


@pytest.fixture
def df():
    return pl.DataFrame({"a": ["x", "y", "x", None, "x"], "b": [1, 1, 2, 2, 1], "w": [1.0, 2.0, 3.0, None, 5.0]})


def test_count_ordenado_por_claves(df):
    out = count(df, f.a)
    assert out["a"].to_list() == ["x", "y", None]
    assert out["n"].to_list() == [3, 1, 1]


def test_count_sort(df):
    assert count(df, f.b, sort=True)["b"].to_list() == [1, 2]


def test_count_sin_columnas(df):
    assert count(df).to_dicts() == [{"n": 5}]


def test_count_wt_ignora_na(df):
    assert count(df, f.b, wt=f.w)["n"].to_list() == [8.0, 3.0]


def test_count_con_expresion(df):
    assert count(df, grande=f.b > 1)["n"].to_list() == [3, 2]


def test_count_nombre_n_existente():
    df = pl.DataFrame({"n": [1, 1, 2]})
    with pytest.warns(DplyrMessage, match="`nn`"):
        out = count(df, f.n)
    assert out.columns == ["n", "nn"]


def test_count_conserva_grupos(df):
    out = df >> group_by(f.a) >> count(f.b)
    assert group_vars(out) == ["a"]


def test_tally(df):
    out = df >> group_by(f.a) >> tally()
    assert out["n"].to_list() == [3, 1, 1]
    assert isinstance(out, pl.DataFrame)


def test_add_count(df):
    out = add_count(df, f.a)
    assert out["n"].to_list() == [3, 1, 3, 1, 3]
    assert out.height == 5


def test_distinct_todas(df):
    d = pl.DataFrame({"x": [1, 1, 2, None, None]})
    assert distinct(d)["x"].to_list() == [1, 2, None]


def test_distinct_columnas(df):
    out = distinct(df, f.a)
    assert out.columns == ["a"]
    assert out["a"].to_list() == ["x", "y", None]


def test_distinct_keep_all(df):
    out = distinct(df, f.b, _keep_all=True)
    assert out.columns == ["a", "b", "w"]
    assert out["w"].to_list() == [1.0, 3.0]


def test_distinct_expresion(df):
    assert distinct(df, grande=f.b > 1).columns == ["grande"]


def test_distinct_agrupado_incluye_grupos(df):
    out = df >> group_by(f.a) >> distinct(f.b)
    assert out.columns == ["a", "b"]
