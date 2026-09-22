import polars as pl
import pytest

from polyr import NA, f, mean, mutate
from polyr.errors import DplyrError


@pytest.fixture
def df():
    return pl.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})


def test_columna_nueva_va_al_final(df):
    out = df >> mutate(z=f.x + f.y)
    assert out.columns == ["x", "y", "z"]
    assert out["z"].to_list() == [11, 22, 33]


def test_se_evalua_en_orden(df):
    out = df >> mutate(z=f.x * 2, w=f.z + 1)
    assert out["w"].to_list() == [3, 5, 7]


def test_sobrescribir_conserva_la_posicion(df):
    out = df >> mutate(x=f.x * 100)
    assert out.columns == ["x", "y"]
    assert out["x"].to_list() == [100, 200, 300]


def test_none_elimina_la_columna(df):
    assert (df >> mutate(x=None)).columns == ["y"]


def test_na_crea_columna_de_na(df):
    assert (df >> mutate(z=NA))["z"].to_list() == [None, None, None]


def test_escalar_se_recicla(df):
    assert (df >> mutate(z=1))["z"].to_list() == [1, 1, 1]


def test_resumen_se_recicla(df):
    assert (df >> mutate(m=mean(f.x)))["m"].to_list() == [2.0, 2.0, 2.0]


def test_vector_de_tamano_n(df):
    assert (df >> mutate(z=[7, 8, 9]))["z"].to_list() == [7, 8, 9]


def test_error_de_tamano(df):
    with pytest.raises(DplyrError, match="tamaño 3 o 1, no 2"):
        df >> mutate(z=[1, 2])


def test_error_si_la_columna_no_existe(df):
    with pytest.raises(DplyrError, match="`nope`"):
        df >> mutate(z=f.nope + 1)


def test_una_columna_puede_llamarse_data(df):
    assert (df >> mutate(data=f.x))["data"].to_list() == [1, 2, 3]


def test_no_modifica_el_original(df):
    df >> mutate(x=None)
    assert df.columns == ["x", "y"]


def test_el_error_indica_el_argumento():
    df = pl.DataFrame({"s": ["a", "b"]})
    with pytest.raises(DplyrError, match=r"En el argumento: `z = s \* 2\.5`"):
        df >> mutate(z=f.s * 2.5)


# --- _keep, _before, _after ------------------------------------------------------

@pytest.fixture
def df4():
    return pl.DataFrame({"a": [1], "b": [2], "c": [3]})


def test_keep_used(df4):
    assert (df4 >> mutate(z=f.a + 1, _keep="used")).columns == ["a", "z"]


def test_keep_unused(df4):
    assert (df4 >> mutate(z=f.a + 1, _keep="unused")).columns == ["b", "c", "z"]


def test_keep_none(df4):
    assert (df4 >> mutate(z=f.a + 1, _keep="none")).columns == ["z"]


def test_keep_conserva_columnas_modificadas(df4):
    assert (df4 >> mutate(b=f.a * 10, _keep="none")).columns == ["b"]


def test_keep_invalido(df4):
    with pytest.raises(DplyrError, match="_keep"):
        df4 >> mutate(z=1, _keep="algunas")


def test_before(df4):
    assert (df4 >> mutate(z=1, _before=f.b)).columns == ["a", "z", "b", "c"]


def test_after(df4):
    assert (df4 >> mutate(z=1, w=2, _after=f.a)).columns == ["a", "z", "w", "b", "c"]


def test_argumento_sin_nombre(df4):
    with pytest.raises(DplyrError, match="deben tener nombre"):
        df4 >> mutate(f.a + 1)


def test_by_agrupa_solo_para_la_operacion():
    df = pl.DataFrame({"g": ["a", "a", "b"], "x": [1, 3, 10]})
    out = df >> mutate(m=mean(f.x), _by=f.g)
    assert out["m"].to_list() == [2.0, 2.0, 10.0]
    assert isinstance(out, pl.DataFrame)
