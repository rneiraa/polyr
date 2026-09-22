import polars as pl
import pytest

from polyr import f, relocate, rename, starts_with
from polyr.errors import DplyrError


@pytest.fixture
def df():
    return pl.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]})


# --- rename ----------------------------------------------------------------------

def test_rename_conserva_orden(df):
    assert rename(df, B=f.b).columns == ["a", "B", "c", "d"]


def test_rename_con_string(df):
    assert rename(df, B="b").columns == ["a", "B", "c", "d"]


def test_rename_colision(df):
    with pytest.raises(DplyrError, match="`a` está repetido"):
        rename(df, a=f.b)


def test_rename_sin_nombre_es_error(df):
    with pytest.raises(DplyrError, match="deben tener nombre"):
        rename(df, f.b)


def test_rename_columna_inexistente(df):
    with pytest.raises(DplyrError, match="`z` no existe"):
        rename(df, nuevo=f.z)


# --- relocate --------------------------------------------------------------------

def test_relocate_al_principio(df):
    assert relocate(df, f.c).columns == ["c", "a", "b", "d"]


def test_relocate_varias_en_orden(df):
    assert relocate(df, f.d, f.b).columns == ["d", "b", "a", "c"]


def test_relocate_before(df):
    assert relocate(df, f.d, _before=f.b).columns == ["a", "d", "b", "c"]


def test_relocate_after(df):
    assert relocate(df, f.a, _after=f.c).columns == ["b", "c", "a", "d"]


def test_relocate_after_ultima(df):
    assert relocate(df, f.a, _after=f.d).columns == ["b", "c", "d", "a"]


def test_relocate_con_selector_como_ancla(df):
    assert relocate(df, f.a, _after=starts_with("b") | starts_with("c")).columns == ["b", "c", "a", "d"]


def test_relocate_renombrando(df):
    assert relocate(df, D=f.d).columns == ["D", "a", "b", "c"]


def test_relocate_before_y_after_es_error(df):
    with pytest.raises(DplyrError, match="no ambos"):
        relocate(df, f.a, _before=f.b, _after=f.c)
