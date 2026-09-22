"""`pick()`: varias columnas entregadas como un solo valor."""
import polars as pl
import pytest

from polyr import (dense_rank, everything, f, group_by, mutate, n_distinct, pick,
                   starts_with, summarise)
from polyr.errors import DplyrError


@pytest.fixture
def df():
    return pl.DataFrame({"g": ["a", "a", "b"], "x": [2, 1, 2], "y": ["p", "q", "p"]})


def test_pick_produce_una_columna_compuesta(df):
    out = df >> mutate(par=pick(f.x, f.y))
    assert out["par"].to_list() == [{"x": 2, "y": "p"}, {"x": 1, "y": "q"}, {"x": 2, "y": "p"}]


def test_pick_ordena_por_todas_las_columnas(df):
    # (1, q) < (2, p): el ranking usa primero x y desempata con y
    assert (df >> mutate(r=dense_rank(pick(f.x, f.y))))["r"].to_list() == [2, 1, 2]


def test_pick_cuenta_combinaciones(df):
    assert (df >> summarise(k=n_distinct(pick(f.x, f.y))))["k"][0] == 2


def test_pick_acepta_selectores(df):
    out = df >> mutate(par=pick(starts_with("x"), f.y))
    assert list(out["par"][0].keys()) == ["x", "y"]


def test_pick_conserva_el_orden_de_la_seleccion(df):
    out = df >> mutate(par=pick(f.y, f.x))
    assert list(out["par"][0].keys()) == ["y", "x"]


def test_pick_no_repite_columnas(df):
    out = df >> mutate(par=pick(f.x, f.x, everything()))
    assert list(out["par"][0].keys()) == ["x", "g", "y"]   # cada columna una vez, en orden


def test_pick_excluye_las_variables_de_agrupacion(df):
    out = df >> group_by(f.g) >> mutate(par=pick(everything()))
    assert list(out["par"][0].keys()) == ["x", "y"]


def test_pick_solo_de_variables_de_agrupacion_es_error(df):
    with pytest.raises(DplyrError, match="al menos una columna"):
        df >> group_by(f.g) >> mutate(par=pick(f.g))


def test_pick_columna_inexistente(df):
    with pytest.raises(DplyrError, match="no existe"):
        df >> mutate(par=pick(f.zzz))


def test_pick_sin_argumentos_es_error():
    with pytest.raises(TypeError, match="al menos una selección"):
        pick()


def test_pick_por_grupo_en_summarise(df):
    out = df >> group_by(f.g) >> summarise(k=n_distinct(pick(everything())))
    assert out["k"].to_list() == [2, 1]


def test_pick_repr(df):
    assert repr(pick(f.x, starts_with("y"))) == "pick(x, starts_with('y'))"


def test_rankings_dejan_na_las_filas_incompletas():
    from polyr import min_rank, ntile, row_number
    d = pl.DataFrame({"x": [2, 1, 2], "y": ["p", "q", None]})
    assert (d >> mutate(r=dense_rank(pick(f.x, f.y))))["r"].to_list() == [2, 1, None]
    assert (d >> mutate(r=min_rank(pick(f.x, f.y))))["r"].to_list() == [2, 1, None]
    assert (d >> mutate(r=row_number(pick(f.x, f.y))))["r"].to_list() == [2, 1, None]
    assert (d >> mutate(r=ntile(pick(f.x, f.y), 2)))["r"].to_list() == [2, 1, None]


def test_rankings_con_nan_en_una_columna_de_pick():
    d = pl.DataFrame({"x": [1.0, 2.0, float("nan")], "y": ["a", "b", "c"]})
    assert (d >> mutate(r=dense_rank(pick(f.x, f.y))))["r"].to_list() == [1, 2, None]
