import polars as pl
import pytest

from polyr import (f, group_by, slice_head, slice_max, slice_min, slice_sample, slice_tail)
from polyr.errors import DplyrError


@pytest.fixture
def df():
    return pl.DataFrame({"g": ["b", "a", "b", "a", "a"], "x": [5, 3, 1, 3, None]})


def test_head_tail(df):
    assert slice_head(df, n=2)["x"].to_list() == [5, 3]
    assert slice_tail(df, n=2)["x"].to_list() == [3, None]


def test_head_negativo(df):
    assert slice_head(df, n=-2).height == 3


def test_head_prop(df):
    assert slice_head(df, prop=0.5).height == 2


def test_head_mayor_que_n(df):
    assert slice_head(df, n=100).height == 5


def test_head_por_grupo_ordenado_por_grupo(df):
    out = df >> group_by(f.g) >> slice_head(n=1)
    assert out["g"].to_list() == ["a", "b"]
    assert out["x"].to_list() == [3, 5]


def test_n_y_prop_es_error(df):
    with pytest.raises(DplyrError, match="no ambos"):
        slice_head(df, n=1, prop=0.5)


def test_slice_min_con_empates(df):
    out = slice_min(df, f.x, n=2)
    assert out["x"].to_list() == [1, 3, 3]


def test_slice_min_sin_empates(df):
    assert slice_min(df, f.x, n=2, with_ties=False)["x"].to_list() == [1, 3]


def test_slice_max(df):
    assert slice_max(df, f.x, n=1)["x"].to_list() == [5]


def test_slice_min_na_completa(df):
    assert slice_min(df, f.x, n=5)["x"].to_list() == [1, 3, 3, 5, None]
    assert slice_min(df, f.x, n=5, na_rm=True)["x"].to_list() == [1, 3, 3, 5]


def test_slice_max_por_grupo(df):
    out = df >> group_by(f.g) >> slice_max(f.x, n=1)
    assert out["g"].to_list() == ["a", "a", "b"]
    assert out["x"].to_list() == [3, 3, 5]


def test_slice_sample_reproducible(df):
    a = slice_sample(df, n=3, seed=42)
    b = slice_sample(df, n=3, seed=42)
    assert a.height == 3 and a.equals(b)


def test_slice_sample_por_grupo(df):
    out = df >> group_by(f.g) >> slice_sample(n=1, seed=1)
    assert sorted(out["g"].to_list()) == ["a", "b"]
