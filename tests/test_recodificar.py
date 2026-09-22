"""`case_match()` y `consecutive_id()`."""
import polars as pl
import pytest

from polyr import (NA, case_match, consecutive_id, f, group_by, max, mutate,
                   summarise)
from polyr.errors import DplyrError, ExprError


def col(df, expr):
    return (df >> mutate(out=expr))["out"].to_list()


@pytest.fixture
def df():
    return pl.DataFrame({"pais": ["CL", "AR", "PE", None], "x": [1, 2, 3, 4]})


# --- case_match ---------------------------------------------------------------------

def test_case_match_lista_y_valor_suelto(df):
    out = col(df, case_match(f.pais, (["CL", "AR"], "Cono Sur"), ("PE", "Andes"),
                             _default="otro"))
    assert out == ["Cono Sur", "Cono Sur", "Andes", "otro"]


def test_case_match_sin_default_deja_na(df):
    assert col(df, case_match(f.pais, ("CL", 1))) == [1, None, None, None]


def test_case_match_na_solo_coincide_si_se_pide(df):
    assert col(df, case_match(f.pais, ([None], "falta"), _default="hay")) == \
        ["hay", "hay", "hay", "falta"]


def test_case_match_gana_el_primer_caso(df):
    assert col(df, case_match(f.pais, ("CL", 1), (["CL", "AR"], 2), _default=0)) == [1, 2, 0, 0]


def test_case_match_numerico(df):
    assert col(df, case_match(f.x, ([1, 2], "bajo"), ([3, 4], "alto"))) == \
        ["bajo", "bajo", "alto", "alto"]


def test_case_match_tipo_comun_de_los_resultados(df):
    # 1 (integer) y 2.5 (double) se combinan a double
    assert col(df, case_match(f.x, (1, 1), ([2, 3, 4], 2.5))) == [1.0, 2.5, 2.5, 2.5]


def test_case_match_resultados_incompatibles_es_error(df):
    with pytest.raises(DplyrError, match="No se puede combinar"):
        df >> mutate(out=case_match(f.x, (1, "uno"), (2, 2)))


def test_case_match_valores_incompatibles_con_x_es_error(df):
    with pytest.raises(DplyrError, match="No se puede combinar"):
        df >> mutate(out=case_match(f.x, ("a", 1)))


def test_case_match_rechaza_condiciones(df):
    with pytest.raises(ExprError, match="case_when"):
        case_match(f.x, (f.x > 1, "sí"))


def test_case_match_necesita_casos(df):
    with pytest.raises(ExprError, match="al menos un caso"):
        case_match(f.x)


def test_case_match_caso_mal_formado(df):
    with pytest.raises(TypeError, match="tupla"):
        case_match(f.x, [1, 2])


def test_case_match_acepta_na_como_resultado(df):
    assert col(df, case_match(f.x, (1, NA), _default=0)) == [None, 0, 0, 0]


# --- consecutive_id -----------------------------------------------------------------

def test_consecutive_id_cuenta_rachas():
    d = pl.DataFrame({"g": ["a", "a", "b", "a"]})
    assert col(d, consecutive_id(f.g)) == [1, 1, 2, 3]


def test_consecutive_id_na_consecutivos_son_la_misma_racha():
    d = pl.DataFrame({"x": [1, None, None, 2]})
    assert col(d, consecutive_id(f.x)) == [1, 2, 2, 3]


def test_consecutive_id_varias_columnas():
    d = pl.DataFrame({"a": [1, 1, 1, 2], "b": ["x", "y", "y", "y"]})
    assert col(d, consecutive_id(f.a, f.b)) == [1, 2, 2, 3]


def test_consecutive_id_una_sola_fila():
    assert col(pl.DataFrame({"x": [7]}), consecutive_id(f.x)) == [1]


def test_consecutive_id_se_reinicia_en_cada_grupo():
    d = pl.DataFrame({"g": ["a", "a", "b", "b"], "x": ["u", "v", "u", "u"]})
    out = d >> group_by(f.g) >> mutate(tramo=consecutive_id(f.x))
    assert out["tramo"].to_list() == [1, 2, 1, 1]


def test_consecutive_id_sirve_para_contar_rachas():
    d = pl.DataFrame({"g": ["a", "a", "b", "b"], "x": ["u", "v", "u", "u"]})
    out = d >> group_by(f.g) >> summarise(rachas=max(consecutive_id(f.x)))
    assert out["rachas"].to_list() == [2, 1]


def test_consecutive_id_necesita_argumentos():
    with pytest.raises(ExprError, match="al menos un argumento"):
        consecutive_id()
