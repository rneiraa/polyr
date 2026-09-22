"""Operaciones de conjuntos sobre filas."""
import polars as pl
import pytest

from polyr import (f, group_by, group_vars, intersect, setdiff, symdiff, union, union_all)
from polyr.errors import DplyrError


@pytest.fixture
def x():
    return pl.DataFrame({"a": [1, 2, 2, None], "b": ["p", "q", "q", "z"]})


@pytest.fixture
def y():
    return pl.DataFrame({"a": [2, 3, None], "b": ["q", "r", "z"]})


def rows(df):
    return list(zip(df["a"].to_list(), df["b"].to_list()))


def test_union_quita_repetidas_y_respeta_el_orden(x, y):
    assert rows(union(x, y)) == [(1, "p"), (2, "q"), (None, "z"), (3, "r")]


def test_union_all_conserva_repetidas(x, y):
    assert union_all(x, y).height == 7
    assert rows(union_all(x, y))[:2] == [(1, "p"), (2, "q")]


def test_intersect_en_el_orden_de_x(x, y):
    assert rows(intersect(x, y)) == [(2, "q"), (None, "z")]   # NA coincide con NA


def test_setdiff(x, y):
    assert rows(setdiff(x, y)) == [(1, "p")]


def test_symdiff_primero_las_de_x(x, y):
    assert rows(symdiff(x, y)) == [(1, "p"), (3, "r")]


def test_funcionan_con_pipe(x, y):
    assert rows(x >> intersect(y)) == [(2, "q"), (None, "z")]


def test_el_orden_de_las_columnas_lo_pone_x(x):
    otra = pl.DataFrame({"b": ["p"], "a": [1]})
    out = intersect(x, otra)
    assert out.columns == ["a", "b"]
    assert rows(out) == [(1, "p")]


def test_tipo_comun_de_las_columnas():
    enteros = pl.DataFrame({"a": [1, 2]})
    dobles = pl.DataFrame({"a": [2.0, 3.0]})
    out = union(enteros, dobles)
    assert out["a"].dtype == pl.Float64
    assert out["a"].to_list() == [1.0, 2.0, 3.0]


def test_tipos_incompatibles_es_error():
    with pytest.raises(DplyrError, match="No se puede combinar"):
        union(pl.DataFrame({"a": [1]}), pl.DataFrame({"a": ["x"]}))


def test_columnas_distintas_es_error(x):
    with pytest.raises(DplyrError, match="Columnas en `y` pero no en `x`: `c`"):
        union(x, pl.DataFrame({"a": [1], "b": ["p"], "c": [0]}))
    with pytest.raises(DplyrError, match="Columnas en `x` pero no en `y`: `b`"):
        union(x, pl.DataFrame({"a": [1]}))


def test_conserva_los_grupos_de_x(x, y):
    out = x >> group_by(f.a) >> union(y)
    assert group_vars(out) == ["a"]


def test_union_de_tabla_vacia(x):
    vacia = x.head(0)
    assert rows(union(x, vacia)) == [(1, "p"), (2, "q"), (None, "z")]
    assert setdiff(vacia, x).height == 0


def test_setdiff_de_todo_deja_vacio(x):
    assert setdiff(x, x).height == 0
    assert symdiff(x, x).height == 0
