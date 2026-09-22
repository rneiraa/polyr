import warnings

import polars as pl
import pytest

from polyr import (DplyrMessage, anti_join, cross_join, f, full_join, group_by, group_vars,
                   inner_join, join_by, left_join, right_join, semi_join)
from polyr.errors import DplyrError


@pytest.fixture
def x():
    return pl.DataFrame({"id": [3, 1, 2, None], "vx": ["c", "a", "b", "na"]})


@pytest.fixture
def y():
    return pl.DataFrame({"id": [1, 1, 4, None], "vy": [10, 11, 40, 99]})


def quiet(fn, *args, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DplyrMessage)
        return fn(*args, **kwargs)


def test_by_natural_informa(x, y):
    with pytest.warns(DplyrMessage, match=r"join_by\(id\)"):
        left_join(x, y)


def test_left_join_orden_de_x_y_na_coincide(x, y):
    out = left_join(x, y, by="id")
    assert out["id"].to_list() == [3, 1, 1, 2, None]
    assert out["vy"].to_list() == [None, 10, 11, None, 99]


def test_na_matches_never(x, y):
    out = left_join(x, y, by="id", na_matches="never")
    assert out.filter(pl.col("id").is_null())["vy"].to_list() == [None]


def test_inner_join(x, y):
    assert inner_join(x, y, by="id")["vx"].to_list() == ["a", "a", "na"]


def test_right_join_sin_pareja_al_final(x, y):
    out = right_join(x, y, by="id")
    assert out["id"].to_list() == [1, 1, None, 4]
    assert out["vx"].to_list() == ["a", "a", "na", None]


def test_full_join(x, y):
    out = full_join(x, y, by="id")
    assert out["id"].to_list() == [3, 1, 1, 2, None, 4]


def test_join_by_con_nombres_distintos():
    a = pl.DataFrame({"k": [1, 2], "va": [1, 2]})
    b = pl.DataFrame({"codigo": [2], "vb": ["dos"]})
    out = left_join(a, b, by=join_by(f.k == f.codigo))
    assert out.columns == ["k", "va", "vb"]
    assert out["vb"].to_list() == [None, "dos"]


def test_by_dict():
    a = pl.DataFrame({"k": [1]})
    b = pl.DataFrame({"c": [1], "v": [5]})
    assert inner_join(a, b, by={"k": "c"})["v"].to_list() == [5]


def test_sufijos():
    a = pl.DataFrame({"id": [1], "v": [1]})
    b = pl.DataFrame({"id": [1], "v": [2]})
    out = left_join(a, b, by="id")
    assert out.columns == ["id", "v.x", "v.y"]
    assert left_join(a, b, by="id", suffix=("_a", "_b")).columns == ["id", "v_a", "v_b"]


def test_tipos_de_claves_comunes():
    a = pl.DataFrame({"id": [1, 2]})
    b = pl.DataFrame({"id": [2.0], "v": [1]})
    assert inner_join(a, b, by="id")["v"].to_list() == [1]


def test_tipos_de_claves_incompatibles():
    a = pl.DataFrame({"id": ["1"]})
    b = pl.DataFrame({"id": [1]})
    with pytest.raises(DplyrError, match=r"No se puede unir `x\$id` <character> con `y\$id` <integer>"):
        inner_join(a, b, by="id")


def test_multiple(x, y):
    assert left_join(x, y, by="id", multiple="first")["vy"].to_list() == [None, 10, None, 99]
    assert left_join(x, y, by="id", multiple="last")["vy"].to_list() == [None, 11, None, 99]


def test_relationship_many_to_one(x, y):
    with pytest.raises(DplyrError, match="La fila 1 de `x` coincide con varias"):
        left_join(x, y, by="id", relationship="many-to-one")


def test_relationship_one_to_one_ok(x):
    y2 = pl.DataFrame({"id": [1, 2], "v": [1, 2]})
    assert left_join(x, y2, by="id", relationship="one-to-one").height == 4


def test_many_to_many_advierte():
    a = pl.DataFrame({"k": [1, 1]})
    b = pl.DataFrame({"k": [1, 1]})
    with pytest.warns(UserWarning, match="muchos-a-muchos"):
        inner_join(a, b, by="k")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert inner_join(a, b, by="k", relationship="many-to-many").height == 4


def test_unmatched_error(x, y):
    with pytest.raises(DplyrError, match="La fila 2 de `y` no tiene pareja"):
        left_join(x, y, by="id", unmatched="error")
    with pytest.raises(DplyrError, match="de `x` no tiene pareja"):
        inner_join(x, y, by="id", unmatched="error")


def test_semi_anti(x, y):
    assert semi_join(x, y, by="id")["vx"].to_list() == ["a", "na"]
    assert anti_join(x, y, by="id")["vx"].to_list() == ["c", "b"]


def test_pipe_y_grupos(x, y):
    out = quiet(lambda: group_by(x, f.vx) >> left_join(y, by="id"))
    assert group_vars(out) == ["vx"]


def test_sin_columnas_comunes():
    with pytest.raises(DplyrError, match="`by` es obligatorio"):
        left_join(pl.DataFrame({"a": [1]}), pl.DataFrame({"b": [1]}))


def test_columna_de_union_inexistente(x, y):
    with pytest.raises(DplyrError, match="No existe `zz`"):
        left_join(x, y, by="zz")


def test_desigualdad_no_implementada(x, y):
    with pytest.raises(DplyrError, match="todavía no están implementadas"):
        left_join(x, y, by=join_by(f.id >= f.id))


def test_cross_join():
    a = pl.DataFrame({"a": [1, 2]})
    b = pl.DataFrame({"b": ["x", "y"]})
    out = cross_join(a, b)
    assert list(zip(out["a"], out["b"])) == [(1, "x"), (1, "y"), (2, "x"), (2, "y")]
