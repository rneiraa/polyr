import polars as pl
import pytest
from polars.testing import assert_frame_equal

from polyr import NA, f, filter, mean
from polyr.errors import DplyrError


@pytest.fixture
def df():
    return pl.DataFrame({"x": [1, 2, 3, None, 5], "y": ["a", "b", "a", "b", "a"]})


def test_pipe_y_llamada_directa_son_equivalentes(df):
    assert_frame_equal(df >> filter(f.x > 2), filter(df, f.x > 2))


def test_sin_condiciones_devuelve_los_datos(df):
    assert_frame_equal(df >> filter(), df)


def test_varias_condiciones_se_combinan_con_and(df):
    assert (df >> filter(f.x > 1, f.y == "a"))["x"].to_list() == [3, 5]


def test_or_y_not(df):
    assert (df >> filter((f.x == 1) | (f.x == 5)))["x"].to_list() == [1, 5]
    assert (df >> filter(~(f.y == "a")))["y"].to_list() == ["b", "b"]


def test_las_filas_con_na_se_descartan(df):
    assert (df >> filter(f.x > 0)).height == 4


def test_condicion_de_tamano_1_se_recicla(df):
    assert (df >> filter(True)).height == 5
    assert (df >> filter(False)).height == 0
    assert (df >> filter(NA)).height == 0


def test_variables_del_entorno_se_capturan(df):
    limite = 3
    assert (df >> filter(f.x >= limite))["x"].to_list() == [3, 5]


def test_nombres_de_columna_con_espacios():
    df = pl.DataFrame({"mi col": [1, 2]})
    assert (df >> filter(f["mi col"] > 1)).height == 1


def test_mean_respeta_la_semantica_de_na_de_r(df):
    # mean(x) con un NA es NA, así que ninguna fila pasa (igual que en R)
    assert (df >> filter(f.x > mean(f.x))).height == 0
    assert (df >> filter(f.x > mean(f.x, na_rm=True)))["x"].to_list() == [3, 5]


def test_error_si_la_condicion_no_es_logica(df):
    with pytest.raises(DplyrError, match="vector lógico"):
        df >> filter(f.x + 1)


def test_error_si_la_columna_no_existe(df):
    with pytest.raises(DplyrError, match="No se encontró la columna `z`"):
        df >> filter(f.z > 1)


def test_error_con_argumento_con_nombre(df):
    with pytest.raises(DplyrError, match=r"f\.x == 1"):
        filter(df, x=1)


def test_error_al_usar_and_de_python(df):
    with pytest.raises(TypeError, match="&"):
        df >> filter(f.x > 1 and f.y == "a")


def test_error_con_comparacion_encadenada(df):
    with pytest.raises(TypeError, match="encadenadas"):
        df >> filter(1 < f.x < 5)
