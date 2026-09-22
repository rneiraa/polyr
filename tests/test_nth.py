"""`nth()`: la única posición de polyr que cuenta desde 1, como en R."""
import polars as pl
import pytest

from polyr import f, group_by, mutate, nth, summarise
from polyr.errors import ExprError

nan = float("nan")


def one(df, expr):
    return (df >> summarise(out=expr))["out"][0]


@pytest.fixture
def df():
    return pl.DataFrame({"x": [10, 20, 30], "orden": [3, 1, 2], "s": ["a", "b", "c"]})


def test_nth_cuenta_desde_uno(df):
    assert one(df, nth(f.x, 1)) == 10
    assert one(df, nth(f.x, 2)) == 20
    assert one(df, nth(f.x, 3)) == 30


def test_nth_negativo_cuenta_desde_el_final(df):
    assert one(df, nth(f.x, -1)) == 30
    assert one(df, nth(f.x, -3)) == 10


def test_nth_fuera_de_rango_da_default(df):
    assert one(df, nth(f.x, 4)) is None
    assert one(df, nth(f.x, -4)) is None
    assert one(df, nth(f.x, 4, default=0)) == 0


def test_nth_order_by(df):
    # ordenado por `orden`: 20, 30, 10
    assert one(df, nth(f.x, 1, order_by=f.orden)) == 20
    assert one(df, nth(f.x, -1, order_by=f.orden)) == 10


def test_nth_na_rm():
    d = pl.DataFrame({"x": [None, 1.0, nan, 2.0]})
    assert one(d, nth(f.x, 1)) is None
    assert one(d, nth(f.x, 1, na_rm=True)) == 1.0
    assert one(d, nth(f.x, 2, na_rm=True)) == 2.0   # NaN también es faltante
    assert one(d, nth(f.x, 3, na_rm=True)) is None


def test_nth_conserva_el_tipo_comun_con_default(df):
    out = df >> summarise(v=nth(f.x, 9, default=1.5))
    assert out["v"].dtype == pl.Float64
    assert out["v"][0] == 1.5


def test_nth_texto(df):
    assert one(df, nth(f.s, 2)) == "b"


def test_nth_por_grupo():
    d = pl.DataFrame({"g": ["a", "a", "b", "b"], "x": [1, 2, 3, 4]})
    out = d >> group_by(f.g) >> summarise(segundo=nth(f.x, 2), ultimo=nth(f.x, -1))
    assert out["segundo"].to_list() == [2, 4]
    assert out["ultimo"].to_list() == [2, 4]


def test_nth_en_mutate_reparte_el_valor(df):
    assert (df >> mutate(primero=nth(f.x, 1)))["primero"].to_list() == [10, 10, 10]


def test_nth_rechaza_cero_y_no_enteros():
    with pytest.raises(ExprError, match="distinto de 0"):
        nth(f.x, 0)
    with pytest.raises(ExprError, match="entero"):
        nth(f.x, 1.5)
