import math

import polars as pl
import pytest

from polyr import NA, coalesce, desc, f, if_else, is_na, mean, mutate, n
from polyr.errors import DplyrError


@pytest.fixture
def df():
    return pl.DataFrame({
        "x": [1.0, None, float("nan"), 4.0],
        "i": [1, 2, 3, 4],
        "b": [True, False, None, True],
        "s": ["a", "b", "c", "d"],
    })


def col(df, expr):
    return (df >> mutate(out=expr))["out"].to_list()


# --- is_na ---------------------------------------------------------------------

def test_is_na_detecta_null_y_nan(df):
    assert col(df, is_na(f.x)) == [False, True, True, False]


def test_is_na_en_no_dobles(df):
    assert col(df, is_na(f.b)) == [False, False, True, False]


# --- mean ----------------------------------------------------------------------

def test_mean_con_na_es_na(df):
    assert col(df, mean(f.x)) == [None] * 4


def test_mean_na_rm_quita_na_y_nan(df):
    assert col(df, mean(f.x, na_rm=True)) == [2.5] * 4


def test_mean_de_nan_sin_na_es_nan():
    out = col(pl.DataFrame({"x": [1.0, float("nan")]}), mean(f.x))
    assert all(math.isnan(v) for v in out)


def test_mean_de_logicos():
    assert col(pl.DataFrame({"b": [True, False, True, True]}), mean(f.b)) == [0.75] * 4


def test_mean_de_texto_es_error(df):
    with pytest.raises(DplyrError, match=r"numérico o lógico, no <character>"):
        df >> mutate(m=mean(f.s))


# --- if_else -------------------------------------------------------------------

def test_if_else_basico(df):
    assert col(df, if_else(f.i > 2, "alto", "bajo")) == ["bajo", "bajo", "alto", "alto"]


def test_if_else_na_en_condicion_da_missing(df):
    # polars devolvería `false` donde la condición es NA; dplyr devuelve NA
    assert col(df, if_else(f.b, 1, 0)) == [1, 0, None, 1]
    assert col(df, if_else(f.b, 1, 0, missing=-1)) == [1, 0, -1, 1]


def test_if_else_lleva_al_tipo_comun(df):
    out = df >> mutate(out=if_else(f.i > 2, f.i, 0.5))
    assert out["out"].dtype == pl.Float64


def test_if_else_tipos_incompatibles(df):
    with pytest.raises(DplyrError, match=r"No se puede combinar `true` <double> con `false` <character>"):
        df >> mutate(out=if_else(f.i > 2, 1.0, "no"))


def test_if_else_condicion_no_logica(df):
    with pytest.raises(DplyrError, match=r"`condition` debe ser un vector lógico, no <integer>"):
        df >> mutate(out=if_else(f.i, 1, 0))


def test_if_else_con_na_como_rama(df):
    assert col(df, if_else(f.i > 2, f.s, NA)) == [None, None, "c", "d"]


# --- coalesce ------------------------------------------------------------------

def test_coalesce_reemplaza_na_y_nan(df):
    assert col(df, coalesce(f.x, 0)) == [1.0, 0.0, 0.0, 4.0]


def test_coalesce_varios_argumentos():
    d = pl.DataFrame({"a": [None, None, 3], "b": [None, 2, 9]})
    assert col(d, coalesce(f.a, f.b, 0)) == [0, 2, 3]


def test_coalesce_tipos_incompatibles(df):
    with pytest.raises(DplyrError, match="No se puede combinar"):
        df >> mutate(out=coalesce(f.x, "cero"))


# --- n y desc ------------------------------------------------------------------

def test_n(df):
    assert col(df, n()) == [4] * 4
    assert col(df, f.i / n()) == [0.25, 0.5, 0.75, 1.0]


def test_desc_fuera_de_arrange_niega(df):
    assert col(df, desc(f.i)) == [-1, -2, -3, -4]


def test_desc_de_texto_fuera_de_arrange(df):
    with pytest.raises(DplyrError, match="desc"):
        df >> mutate(out=desc(f.s))


# --- aritmética con semántica de R ---------------------------------------------

def test_potencia_siempre_es_double():
    out = pl.DataFrame({"i": [2, 3]}) >> mutate(p=f.i ** 2)
    assert out["p"].dtype == pl.Float64


def test_modulo_y_division_entera_como_r():
    # R: 5 %% -3 == -1 ; -5 %% 3 == 1 ; 5 %/% -3 == -2
    d = pl.DataFrame({"a": [5, -5], "b": [-3, 3]})
    out = d >> mutate(m=f.a % f.b, q=f.a // f.b)
    assert out["m"].to_list() == [-1, 1]
    assert out["q"].to_list() == [-2, -2]
