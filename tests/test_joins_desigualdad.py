"""Uniones por desigualdad, por rango y `closest()`."""
import warnings

import polars as pl
import pytest

from polyr import (anti_join, between, closest, f, full_join, inner_join, join_by, left_join,
                   nest_join, overlaps, right_join, semi_join, within)
from polyr.errors import DplyrError


@pytest.fixture
def ventas():
    return pl.DataFrame({"tienda": ["A", "A", "B"], "dia": [3, 8, 5], "monto": [10, 20, 30]})


@pytest.fixture
def tarifas():
    return pl.DataFrame({"tienda": ["A", "A", "B"], "desde": [1, 6, 1], "hasta": [5, 10, 10],
                         "tasa": [0.1, 0.2, 0.3]})


@pytest.fixture
def cortes():
    return pl.DataFrame({"corte": [1, 5, 9], "etiqueta": ["bajo", "medio", "alto"]})


# --- desigualdades ------------------------------------------------------------------

def test_desigualdad_suelta(ventas, cortes):
    out = inner_join(ventas.select("dia"), cortes, by=join_by(f.dia > f.corte))
    assert list(zip(out["dia"], out["corte"])) == [(3, 1), (8, 1), (8, 5), (5, 1)]


def test_dos_desigualdades_delimitan_un_rango(ventas, cortes):
    out = inner_join(ventas.select("dia"), cortes,
                     by=join_by(f.dia >= f.corte, f.dia <= f.corte))
    assert list(zip(out["dia"], out["corte"])) == [(5, 5)]


def test_igualdad_y_desigualdad_juntas(ventas, tarifas):
    out = inner_join(ventas, tarifas, by=join_by(f.tienda, f.dia >= f.desde, f.dia <= f.hasta))
    assert out["tasa"].to_list() == [0.1, 0.2, 0.3]
    assert out["tienda"].to_list() == ["A", "A", "B"]


def test_left_join_por_desigualdad_deja_na(ventas, cortes):
    out = left_join(ventas, cortes, by=join_by(f.dia < f.corte))
    # dia=3 empareja con 5 y 9; dia=8 con 9; dia=5 con 9
    assert out["corte"].to_list() == [5, 9, 9, 9]
    sin_pareja = left_join(pl.DataFrame({"dia": [100]}), cortes, by=join_by(f.dia < f.corte))
    assert sin_pareja["etiqueta"].to_list() == [None]


def test_las_columnas_de_desigualdad_se_conservan_de_las_dos_tablas(ventas, cortes):
    out = inner_join(ventas, cortes, by=join_by(f.dia > f.corte))
    assert "dia" in out.columns and "corte" in out.columns


def test_desigualdad_no_avisa_de_muchos_a_muchos(ventas, cortes):
    with warnings.catch_warnings():
        warnings.simplefilter("error")   # cualquier aviso haría fallar el test
        inner_join(ventas.select("dia"), cortes, by=join_by(f.dia > f.corte))


def test_na_nunca_cumple_una_desigualdad(cortes):
    x = pl.DataFrame({"dia": [None, 3]}, schema={"dia": pl.Int64})
    out = left_join(x, cortes, by=join_by(f.dia > f.corte))
    assert out["corte"].to_list() == [None, 1]


def test_semi_y_anti_join_por_desigualdad(ventas, cortes):
    assert semi_join(ventas, cortes, by=join_by(f.dia > f.corte))["dia"].to_list() == [3, 8, 5]
    lejos = pl.DataFrame({"dia": [0, 7]})
    assert anti_join(lejos, cortes, by=join_by(f.dia > f.corte))["dia"].to_list() == [0]


def test_nest_join_por_desigualdad(ventas, cortes):
    out = nest_join(ventas.select("dia"), cortes, by=join_by(f.dia > f.corte))
    assert [len(c) for c in out["y"]] == [1, 2, 1]


def test_right_y_full_join_por_desigualdad(ventas, cortes):
    derecha = right_join(ventas.select("dia"), cortes, by=join_by(f.dia > f.corte))
    assert derecha["etiqueta"].to_list() == ["bajo", "bajo", "medio", "bajo", "alto"]
    assert derecha["dia"].to_list() == [3, 8, 8, 5, None]
    completa = full_join(pl.DataFrame({"dia": [100]}), cortes, by=join_by(f.dia < f.corte))
    assert completa.height == 4


# --- between / within / overlaps -----------------------------------------------------

def test_between_en_join_by(ventas, tarifas):
    out = inner_join(ventas, tarifas, by=join_by(f.tienda, between(f.dia, f.desde, f.hasta)))
    assert out["tasa"].to_list() == [0.1, 0.2, 0.3]


def test_between_con_bounds_excluye_el_extremo():
    x = pl.DataFrame({"v": [5]})
    y = pl.DataFrame({"lo": [1], "hi": [5]})
    assert inner_join(x, y, by=join_by(between(f.v, f.lo, f.hi))).height == 1
    assert inner_join(x, y, by=join_by(between(f.v, f.lo, f.hi, bounds="[)"))).height == 0


def test_within():
    a = pl.DataFrame({"ini": [2, 1], "fin": [4, 9]})
    b = pl.DataFrame({"i2": [1, 5], "f2": [5, 8]})
    out = inner_join(a, b, by=join_by(within(f.ini, f.fin, f.i2, f.f2)))
    assert list(zip(out["ini"], out["i2"])) == [(2, 1)]


def test_overlaps():
    a = pl.DataFrame({"ini": [2, 1], "fin": [4, 9]})
    b = pl.DataFrame({"i2": [1, 5], "f2": [5, 8]})
    out = inner_join(a, b, by=join_by(overlaps(f.ini, f.fin, f.i2, f.f2)))
    assert list(zip(out["ini"], out["i2"])) == [(2, 1), (1, 1), (1, 5)]


def test_overlaps_bounds_abiertos_excluyen_el_contacto():
    a = pl.DataFrame({"ini": [5], "fin": [8]})
    b = pl.DataFrame({"i2": [1], "f2": [5]})   # se tocan solo en 5
    assert inner_join(a, b, by=join_by(overlaps(f.ini, f.fin, f.i2, f.f2))).height == 1
    assert inner_join(a, b, by=join_by(overlaps(f.ini, f.fin, f.i2, f.f2,
                                                bounds="()"))).height == 0


def test_bounds_no_valido():
    with pytest.raises(DplyrError, match="`bounds` debe ser uno de"):
        join_by(overlaps(f.a, f.b, f.c, f.d, bounds="><"))


# --- closest -------------------------------------------------------------------------

def test_closest_toma_la_pareja_mas_cercana(ventas, cortes):
    out = left_join(ventas, cortes, by=join_by(closest(f.dia >= f.corte)))
    assert out["corte"].to_list() == [1, 5, 5]
    assert out["etiqueta"].to_list() == ["bajo", "medio", "medio"]


def test_closest_hacia_arriba(ventas, cortes):
    out = left_join(ventas, cortes, by=join_by(closest(f.dia <= f.corte)))
    assert out["corte"].to_list() == [5, 9, 5]


def test_closest_sin_pareja(cortes):
    x = pl.DataFrame({"dia": [0]})
    assert left_join(x, cortes, by=join_by(closest(f.dia >= f.corte)))["corte"].to_list() == [None]


def test_closest_conserva_los_empates():
    x = pl.DataFrame({"t": [10]})
    y = pl.DataFrame({"t0": [5, 5], "quien": ["a", "b"]})
    out = inner_join(x, y, by=join_by(closest(f.t >= f.t0)))
    assert out["quien"].to_list() == ["a", "b"]


def test_closest_dentro_de_cada_grupo():
    x = pl.DataFrame({"g": ["a", "b"], "t": [10, 10]})
    y = pl.DataFrame({"g": ["a", "a", "b"], "t0": [1, 8, 3], "v": [1, 2, 3]})
    out = inner_join(x, y, by=join_by(f.g, closest(f.t >= f.t0)))
    assert out["v"].to_list() == [2, 3]


def test_closest_necesita_una_desigualdad():
    with pytest.raises(DplyrError, match="necesita una sola desigualdad"):
        closest(f.a == f.b)


# --- keep -----------------------------------------------------------------------------

def test_keep_false_con_desigualdad_es_error(ventas, cortes):
    with pytest.raises(DplyrError, match="`keep=False` no se puede usar"):
        left_join(ventas, cortes, by=join_by(f.dia > f.corte), keep=False)


def test_keep_true_con_igualdad_y_desigualdad(ventas, tarifas):
    out = inner_join(ventas, tarifas, by=join_by(f.tienda, between(f.dia, f.desde, f.hasta)),
                     keep=True)
    assert out.columns == ["tienda.x", "dia", "monto", "tienda.y", "desde", "hasta", "tasa"]


def test_relationship_se_sigue_comprobando(ventas, cortes):
    with pytest.raises(DplyrError, match="debe coincidir con 1 fila"):
        inner_join(ventas, cortes, by=join_by(f.dia > f.corte), relationship="many-to-one")


def test_repr_de_join_by():
    assert repr(join_by(f.tienda, closest(f.dia >= f.corte))) == \
        "join_by(tienda, closest(dia >= corte))"
    assert repr(join_by(between(f.v, f.lo, f.hi))) == "join_by(v >= lo, v <= hi)"

