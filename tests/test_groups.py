import warnings

import polars as pl
import pytest

from polyr import (DplyrMessage, GroupedFrame, arrange, f, filter, group_by, group_keys,
                   group_vars, mean, mutate, n, n_groups, rename, select, summarise, ungroup)
from polyr.errors import DplyrError


@pytest.fixture
def df():
    return pl.DataFrame({
        "g": ["b", "a", "b", None, "a"],
        "h": [1, 1, 2, 2, 1],
        "x": [1.0, 2.0, 3.0, 4.0, 5.0],
    })


def test_group_by_crea_grouped_frame(df):
    gdf = group_by(df, f.g)
    assert isinstance(gdf, GroupedFrame)
    assert group_vars(gdf) == ["g"]
    assert n_groups(gdf) == 3


def test_group_keys_ordenadas_con_na_al_final(df):
    assert group_keys(group_by(df, f.g))["g"].to_list() == ["a", "b", None]


def test_group_by_con_expresion(df):
    gdf = df >> group_by(alto=f.x > 2)
    assert group_vars(gdf) == ["alto"]
    assert "alto" in gdf.columns


def test_group_by_expresion_sin_nombre_es_error(df):
    with pytest.raises(DplyrError, match="deben tener nombre"):
        group_by(df, f.x > 2)


def test_group_by_reemplaza_o_agrega(df):
    assert group_vars(df >> group_by(f.g) >> group_by(f.h)) == ["h"]
    assert group_vars(df >> group_by(f.g) >> group_by(f.h, _add=True)) == ["g", "h"]


def test_ungroup(df):
    assert isinstance(ungroup(group_by(df, f.g)), pl.DataFrame)
    assert group_vars(df >> group_by(f.g, f.h) >> ungroup(f.g)) == ["h"]


def test_repr(df):
    assert repr(group_by(df, f.g)).startswith("# Grupos: g [3]")


def test_mutate_por_grupo_conserva_orden(df):
    out = df >> group_by(f.g) >> mutate(m=mean(f.x), k=n())
    assert out["m"].to_list() == [2.0, 3.5, 2.0, 4.0, 3.5]
    assert out["k"].to_list() == [2, 2, 2, 1, 2]
    assert group_vars(out) == ["g"]


def test_filter_por_grupo(df):
    out = df >> group_by(f.g) >> filter(f.x >= mean(f.x))
    assert out["x"].to_list() == [3.0, 4.0, 5.0]
    assert group_vars(out) == ["g"]


def test_by_con_datos_agrupados_es_error(df):
    with pytest.raises(DplyrError, match="`_by`"):
        group_by(df, f.g) >> mutate(z=1, _by=f.h)


def test_select_agrega_variables_de_grupo(df):
    with pytest.warns(DplyrMessage, match="`g`"):
        out = group_by(df, f.g) >> select(f.x)
    assert out.columns == ["g", "x"]


def test_rename_actualiza_grupos(df):
    assert group_vars(group_by(df, f.g) >> rename(grupo=f.g)) == ["grupo"]


def test_arrange_ignora_grupos_salvo_by_group(df):
    gdf = group_by(df, f.g)
    assert arrange(gdf, f.x)["x"].to_list() == [1.0, 2.0, 3.0, 4.0, 5.0]
    out = arrange(gdf, f.x, _by_group=True)
    assert out["g"].to_list() == ["a", "a", "b", "b", None]


def test_no_se_puede_eliminar_variable_de_grupo(df):
    with pytest.raises(DplyrError, match="agrupación"):
        group_by(df, f.g) >> mutate(g=None)


# --- summarise ---------------------------------------------------------------------

def test_summarise_sin_grupos(df):
    out = df >> summarise(m=mean(f.x), k=n())
    assert out.to_dicts() == [{"m": 3.0, "k": 5}]


def test_summarise_por_grupo_ordenado(df):
    out = df >> group_by(f.g) >> summarise(m=mean(f.x))
    assert out["g"].to_list() == ["a", "b", None]
    assert out["m"].to_list() == [3.5, 2.0, 4.0]
    assert isinstance(out, pl.DataFrame)  # un solo grupo: se elimina


def test_summarise_secuencial(df):
    out = df >> group_by(f.g) >> summarise(m=mean(f.x), doble=f.m * 2)
    assert out["doble"].to_list() == [7.0, 4.0, 8.0]


def test_summarise_sobrescribe_columna(df):
    out = df >> group_by(f.g) >> summarise(x=mean(f.x), y=f.x + 1)
    assert out["y"].to_list() == [4.5, 3.0, 5.0]


def test_summarise_varios_grupos_informa_y_quita_el_ultimo(df):
    with pytest.warns(DplyrMessage, match="_groups"):
        out = df >> group_by(f.g, f.h) >> summarise(k=n())
    assert group_vars(out) == ["g"]


@pytest.mark.parametrize("mode, expected", [("drop", []), ("keep", ["g", "h"]),
                                            ("drop_last", ["g"])])
def test_summarise_groups(df, mode, expected):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = df >> group_by(f.g, f.h) >> summarise(k=n(), _groups=mode)
    assert group_vars(out) == expected


def test_summarise_by(df):
    out = df >> summarise(m=mean(f.x), _by=["g", "h"])
    assert isinstance(out, pl.DataFrame)
    assert out.columns == ["g", "h", "m"]


def test_summarise_tamano_distinto_de_1_es_error(df):
    with pytest.raises(DplyrError, match="tamaño 1"):
        df >> group_by(f.g) >> summarise(y=f.x)


def test_summarise_tamano_1_por_grupo_se_acepta():
    df = pl.DataFrame({"g": ["a", "b"], "x": [1, 2]})
    assert (df >> group_by(f.g) >> summarise(y=f.x))["y"].to_list() == [1, 2]


def test_summarise_datos_vacios():
    df = pl.DataFrame({"g": pl.Series([], dtype=pl.String), "x": pl.Series([], dtype=pl.Float64)})
    assert (df >> group_by(f.g) >> summarise(m=mean(f.x))).height == 0
    assert (df >> summarise(k=n()))["k"].to_list() == [0]


def test_summarise_no_puede_modificar_grupo(df):
    with pytest.raises(DplyrError, match="agrupación"):
        df >> group_by(f.g) >> summarise(g=n())
