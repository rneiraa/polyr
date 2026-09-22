"""`keep=True`: conservar las columnas de clave de las dos tablas."""
import polars as pl
import pytest

from polyr import f, full_join, inner_join, join_by, left_join, right_join
from polyr.errors import DplyrError


@pytest.fixture
def x():
    return pl.DataFrame({"id": [3, 1, 2, None], "vx": ["c", "a", "b", "na"]})


@pytest.fixture
def y():
    return pl.DataFrame({"id": [1, 1, 4, None], "vy": [10, 11, 40, 99]})


def test_keep_true_separa_las_claves_con_sufijos(x, y):
    out = left_join(x, y, by="id", keep=True)
    assert out.columns == ["id.x", "vx", "id.y", "vy"]
    assert out["id.x"].to_list() == [3, 1, 1, 2, None]
    assert out["id.y"].to_list() == [None, 1, 1, None, None]


def test_keep_por_defecto_funde_las_claves(x, y):
    out = left_join(x, y, by="id")
    assert out.columns == ["id", "vx", "vy"]
    assert left_join(x, y, by="id", keep=False).columns == ["id", "vx", "vy"]


def test_keep_true_con_nombres_distintos_no_pone_sufijos(x):
    z = pl.DataFrame({"codigo": [1, 4], "vy": [10, 40]})
    out = left_join(x, z, by=join_by(f.id == f.codigo), keep=True)
    assert out.columns == ["id", "vx", "codigo", "vy"]
    assert out["codigo"].to_list() == [None, 1, None, None]


def test_keep_true_en_right_join_deja_na_en_la_clave_de_x(x, y):
    out = right_join(x, y, by="id", keep=True)
    assert out["id.x"].to_list() == [1, 1, None, None]
    assert out["id.y"].to_list() == [1, 1, None, 4]


def test_keep_true_en_full_join(x, y):
    out = full_join(x, y, by="id", keep=True)
    assert out.height == 6
    assert out["id.y"].to_list()[-1] == 4
    assert out["id.x"].to_list()[-1] is None


def test_keep_true_en_inner_join(x, y):
    out = inner_join(x, y, by="id", keep=True)
    assert out["vx"].to_list() == ["a", "a", "na"]
    assert out["id.y"].to_list() == [1, 1, None]


def test_keep_true_respeta_suffix(x, y):
    out = left_join(x, y, by="id", keep=True, suffix=("_izq", "_der"))
    assert out.columns == ["id_izq", "vx", "id_der", "vy"]


def test_keep_true_con_varias_claves():
    a = pl.DataFrame({"g": ["a", "b"], "n": [1, 2], "v": [10, 20]})
    b = pl.DataFrame({"g": ["a"], "n": [1], "w": [100]})
    out = left_join(a, b, by=["g", "n"], keep=True)
    assert out.columns == ["g.x", "n.x", "v", "g.y", "n.y", "w"]
    assert out["g.y"].to_list() == ["a", None]


def test_keep_valor_no_valido(x, y):
    with pytest.raises(DplyrError, match="`keep` debe ser True, False o None"):
        left_join(x, y, by="id", keep="sí")
