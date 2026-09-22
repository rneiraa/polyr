import polars as pl
import pytest

from polyr import (all_of, any_of, contains, ends_with, everything, f, is_numeric,
                 last_col, matches, mutate, num_range, pull, rename, select, starts_with, where)
from polyr.errors import DplyrError


@pytest.fixture
def df():
    return pl.DataFrame({
        "id": [1, 2], "Nombre": ["a", "b"], "x1": [1.0, 2.0],
        "x2": [3.0, 4.0], "x10": [5.0, 6.0], "y_total": [7, 8],
    })


def cols(df, *args, **kwargs):
    return select(df, *args, **kwargs).columns


def test_por_nombre_y_string(df):
    assert cols(df, f.x1, "id") == ["x1", "id"]


def test_el_orden_es_el_de_aparicion(df):
    assert cols(df, f.x2, f.id, f.x2) == ["x2", "id"]


def test_rango(df):
    assert cols(df, f["Nombre":"x2"]) == ["Nombre", "x1", "x2"]
    assert cols(df, f["x10":]) == ["x10", "y_total"]
    assert cols(df, f[:"Nombre"]) == ["id", "Nombre"]


def test_rango_invertido(df):
    assert cols(df, f["x2":"Nombre"]) == ["x2", "x1", "Nombre"]


def test_exclusion_al_inicio_parte_de_todo(df):
    assert cols(df, -f.id) == ["Nombre", "x1", "x2", "x10", "y_total"]


def test_exclusion_despues_de_una_seleccion(df):
    assert cols(df, starts_with("x"), -f.x10) == ["x1", "x2"]


def test_complemento(df):
    assert cols(df, ~starts_with("x")) == ["id", "Nombre", "y_total"]


def test_union_e_interseccion(df):
    assert cols(df, f.id | ends_with("total")) == ["id", "y_total"]
    assert cols(df, starts_with("x") & ends_with("0")) == ["x10"]


def test_helpers_ignoran_mayusculas_por_defecto(df):
    assert cols(df, starts_with("nom")) == ["Nombre"]
    assert cols(df, starts_with("nom", ignore_case=False)) == []


def test_contains_y_matches(df):
    assert cols(df, contains("_")) == ["y_total"]
    assert cols(df, matches(r"^x\d$")) == ["x1", "x2"]


def test_num_range(df):
    assert cols(df, num_range("x", range(1, 3))) == ["x1", "x2"]


def test_everything_para_reordenar(df):
    assert cols(df, f.y_total, everything())[:2] == ["y_total", "id"]


def test_last_col(df):
    assert cols(df, last_col()) == ["y_total"]
    assert cols(df, last_col(1)) == ["x10"]


def test_where(df):
    assert cols(df, where(is_numeric)) == ["id", "x1", "x2", "x10", "y_total"]
    assert cols(df, where(lambda s: s.dtype == pl.String)) == ["Nombre"]


def test_where_predicado_no_booleano(df):
    with pytest.raises(DplyrError, match="True o False"):
        select(df, where(lambda s: "si"))


def test_all_of_y_any_of(df):
    assert cols(df, all_of(["x1", "id"])) == ["x1", "id"]
    assert cols(df, any_of(["x1", "no_existe"])) == ["x1"]
    with pytest.raises(DplyrError, match="`no_existe` no existe"):
        select(df, all_of(["x1", "no_existe"]))


def test_lista_de_nombres(df):
    assert cols(df, ["x2", "x1"]) == ["x2", "x1"]


def test_renombrar_al_seleccionar(df):
    assert cols(df, f.id, nombre=f.Nombre) == ["id", "nombre"]


def test_renombrar_conserva_la_posicion_ya_seleccionada(df):
    assert cols(df, everything(), ident=f.id)[0] == "ident"


def test_columna_inexistente(df):
    with pytest.raises(DplyrError, match="La columna `z` no existe"):
        select(df, f.z)


def test_nombres_duplicados(df):
    with pytest.raises(DplyrError, match="únicos"):
        select(df, f.x1, x1=f.x2)


def test_expresion_no_es_seleccion(df):
    with pytest.raises(DplyrError, match="no es una selección de columnas válida"):
        select(df, f.x1 + 1)


def test_selector_fuera_de_select(df):
    with pytest.raises(DplyrError, match="selector de columnas"):
        df >> mutate(z=starts_with("x"))


def test_pipe(df):
    assert (df >> select(f.id)).columns == ["id"]


# --- pull ------------------------------------------------------------------------

def test_pull_por_defecto_ultima(df):
    assert pull(df).to_list() == [7, 8]


def test_pull_por_nombre(df):
    assert (df >> pull(f.x1)).to_list() == [1.0, 2.0]
    assert pull(df, "id").to_list() == [1, 2]


def test_pull_varias_columnas_es_error(df):
    with pytest.raises(DplyrError, match="exactamente una"):
        pull(df, starts_with("x"))


# --- renombrado múltiple con sufijos ---------------------------------------------

def test_select_renombre_multiple_numera_las_columnas():
    d = pl.DataFrame({"a1": [1], "a2": [2], "b": [3]})
    out = d >> select(x=starts_with("a"))
    assert out.columns == ["x1", "x2"]


def test_select_renombre_de_una_sola_columna_no_lleva_sufijo():
    d = pl.DataFrame({"a1": [1], "b": [2]})
    assert (d >> select(x=starts_with("a"))).columns == ["x"]


def test_select_renombre_multiple_conserva_el_orden_de_la_seleccion():
    d = pl.DataFrame({"b": [1], "a2": [2], "a1": [3]})
    assert (d >> select(v=starts_with("a"))).columns == ["v1", "v2"]


def test_rename_sigue_exigiendo_una_sola_columna():
    d = pl.DataFrame({"a1": [1], "a2": [2]})
    with pytest.raises(DplyrError, match="exactamente una columna"):
        d >> rename(x=starts_with("a"))


def test_renombre_sin_coincidencias_es_error():
    d = pl.DataFrame({"a": [1]})
    with pytest.raises(DplyrError, match="no seleccionó ninguna columna"):
        d >> select(x=starts_with("z"))
