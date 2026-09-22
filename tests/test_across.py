import polars as pl
import pytest

from polyr import (across, f, filter, group_by, if_all, if_any, is_numeric, max, mean,
                   mutate, starts_with, summarise, where)
from polyr.errors import DplyrError


@pytest.fixture
def df():
    return pl.DataFrame({"g": ["a", "a", "b"], "x1": [1, 2, 3], "x2": [10, 20, None], "s": ["p", "q", "r"]})


def test_across_mutate(df):
    out = df >> mutate(across(starts_with("x"), lambda c: c * 2))
    assert out.columns == ["g", "x1", "x2", "s"]
    assert out["x1"].to_list() == [2, 4, 6]


def test_across_names(df):
    out = df >> mutate(across(starts_with("x"), lambda c: c + 1, names="{col}_mas"))
    assert out.columns[-2:] == ["x1_mas", "x2_mas"]


def test_across_dict(df):
    out = df >> summarise(across(where(is_numeric), {"m": lambda c: mean(c, na_rm=True), "max": max}))
    assert out.columns == ["x1_m", "x1_max", "x2_m", "x2_max"]
    assert out["x2_max"].to_list() == [None]


def test_across_excluye_grupos(df):
    out = df >> group_by(f.g) >> summarise(across(~f.s, mean))
    assert out.columns == ["g", "x1", "x2"]
    assert out["x1"].to_list() == [1.5, 3.0]


def test_across_ve_columnas_previas(df):
    out = df >> mutate(y1=f.x1, yy=f.x1, _keep="none") >> mutate(across(starts_with("y"), lambda c: -c))
    assert out["yy"].to_list() == [-1, -2, -3]


def test_across_nombres_duplicados(df):
    with pytest.raises(DplyrError, match="más de una vez"):
        df >> mutate(across(starts_with("x"), lambda c: c, names="dup"))


def test_if_any_if_all(df):
    assert (df >> filter(if_any(starts_with("x"), lambda c: c > 15))).height == 1
    assert (df >> filter(if_all(starts_with("x"), lambda c: c > 1))).height == 1


def test_if_any_con_na():
    d = pl.DataFrame({"a": [None, None], "b": [True, False]})
    out = d >> mutate(any=if_any(~f.b, lambda c: c > 0), all_=if_all(f.b, lambda c: c))
    assert out["any"].to_list() == [None, None]


def test_if_any_funcion_no_logica(df):
    with pytest.raises(DplyrError, match="lógico"):
        df >> filter(if_any(starts_with("x"), lambda c: c + 1))
