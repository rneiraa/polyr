"""`nest_join()`: las parejas de `y` guardadas en una celda por fila de `x`."""
import polars as pl
import pytest

from polyr import f, group_by, group_vars, join_by, nest_join
from polyr.errors import DplyrError


@pytest.fixture
def x():
    return pl.DataFrame({"id": [3, 1, 2, None], "vx": ["c", "a", "b", "na"]})


@pytest.fixture
def y():
    return pl.DataFrame({"id": [1, 1, 4, None], "vy": [10, 11, 40, 99]})


def test_nest_join_conserva_las_filas_de_x(x, y):
    out = nest_join(x, y, by="id")
    assert out.height == x.height
    assert out.columns == ["id", "vx", "y"]
    assert out["id"].to_list() == [3, 1, 2, None]


def test_las_parejas_van_juntas_en_una_celda(x, y):
    out = nest_join(x, y, by="id")
    assert out["y"].to_list() == [[], [{"vy": 10}, {"vy": 11}], [], [{"vy": 99}]]


def test_sin_parejas_la_celda_queda_vacia_no_na(x, y):
    celda = nest_join(x, y, by="id")["y"][0]
    assert len(celda) == 0
    assert celda.struct.unnest().height == 0


def test_la_celda_se_convierte_en_tabla(x, y):
    celda = nest_join(x, y, by="id")["y"][1]
    assert celda.struct.unnest()["vy"].to_list() == [10, 11]


def test_na_matches_never(x, y):
    out = nest_join(x, y, by="id", na_matches="never")
    assert out["y"].to_list()[-1] == []


def test_keep_true_guarda_la_clave_de_y(x, y):
    out = nest_join(x, y, by="id", keep=True)
    assert out["y"].to_list()[1] == [{"id": 1, "vy": 10}, {"id": 1, "vy": 11}]


def test_claves_con_nombres_distintos(x):
    z = pl.DataFrame({"codigo": [1, 1], "vy": [10, 11]})
    out = nest_join(x, z, by=join_by(f.id == f.codigo))
    assert out["y"].to_list()[1] == [{"vy": 10}, {"vy": 11}]


def test_name_cambia_el_nombre_de_la_columna(x, y):
    assert nest_join(x, y, by="id", name="parejas").columns[-1] == "parejas"


def test_name_repetido_es_error(x):
    z = pl.DataFrame({"id": [1], "vx2": [0]})
    with pytest.raises(DplyrError, match="ya es una columna de `x`"):
        nest_join(x, z, by="id", name="vx")


def test_conserva_los_grupos_de_x(x, y):
    out = x >> group_by(f.vx) >> nest_join(y, by="id")
    assert group_vars(out) == ["vx"]


def test_funciona_con_pipe(x, y):
    assert (x >> nest_join(y, by="id")).height == 4


def test_keep_no_valido(x, y):
    with pytest.raises(DplyrError, match="`keep` debe ser True, False o None"):
        nest_join(x, y, by="id", keep="sí")
