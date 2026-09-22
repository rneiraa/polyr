"""Resúmenes de base R: any/all con lógica de tres valores, quantile, IQR, mad."""
import polars as pl
import pytest

from polyr import (IQR, all, any, f, group_by, mad, mutate, quantile, reframe, summarise)
from polyr.errors import DplyrError, ExprError

nan = float("nan")


def one(df, expr):
    return (df >> summarise(out=expr))["out"][0]


def logical(values):
    return pl.DataFrame({"b": pl.Series(values, dtype=pl.Boolean)})


# --- any / all ----------------------------------------------------------------------

@pytest.mark.parametrize("values, esperado", [
    ([True, False], True),
    ([True, None], True),          # un TRUE decide aunque haya NA
    ([False, None], None),         # sin TRUE, el NA deja el resultado indeciso
    ([False, False], False),
    ([], False),                   # any(logical(0)) es FALSE
])
def test_any_logica_de_tres_valores(values, esperado):
    assert one(logical(values), any(f.b)) is esperado


@pytest.mark.parametrize("values, esperado", [
    ([True, True], True),
    ([False, None], False),        # un FALSE decide aunque haya NA
    ([True, None], None),
    ([True, False], False),
    ([], True),                    # all(logical(0)) es TRUE
])
def test_all_logica_de_tres_valores(values, esperado):
    assert one(logical(values), all(f.b)) is esperado


def test_any_all_na_rm():
    assert one(logical([False, None]), any(f.b, na_rm=True)) is False
    assert one(logical([False, None]), all(f.b, na_rm=True)) is False
    assert one(logical([True, None]), any(f.b, na_rm=True)) is True
    assert one(logical([True, None]), all(f.b, na_rm=True)) is True


def test_any_all_necesitan_logicos():
    df = pl.DataFrame({"x": [1, 2]})
    with pytest.raises(DplyrError, match="necesita un vector lógico"):
        df >> summarise(out=any(f.x))


def test_any_por_grupo():
    df = pl.DataFrame({"g": ["a", "a", "b", "b"], "b": [True, False, False, False]})
    out = df >> group_by(f.g) >> summarise(hay=any(f.b), todos=all(f.b))
    assert out["hay"].to_list() == [True, False]
    assert out["todos"].to_list() == [False, False]


# --- quantile -----------------------------------------------------------------------

@pytest.fixture
def q():
    return pl.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})


def test_quantile_interpolacion_de_r(q):
    assert one(q, quantile(f.x, 0.25)) == 1.75   # type = 7 de R
    assert one(q, quantile(f.x, 0.5)) == 2.5
    assert one(q, quantile(f.x, 1)) == 4.0


def test_quantile_con_na_es_na():
    df = pl.DataFrame({"x": [1.0, None, 3.0]})
    assert one(df, quantile(f.x, 0.5)) is None
    assert one(df, quantile(f.x, 0.5, na_rm=True)) == 2.0


def test_quantile_nan_tambien_es_faltante():
    df = pl.DataFrame({"x": [1.0, nan, 3.0]})
    assert one(df, quantile(f.x, 0.5)) is None
    assert one(df, quantile(f.x, 0.5, na_rm=True)) == 2.0


def test_quantile_varios_probs_en_reframe(q):
    out = q >> reframe(p=quantile(f.x, [0.25, 0.75]))
    assert out["p"].to_list() == [1.75, 3.25]


def test_quantile_varios_probs_no_cabe_en_summarise(q):
    with pytest.raises(DplyrError, match="tamaño 1"):
        q >> summarise(p=quantile(f.x, [0.25, 0.75]))


def test_quantile_valida_probs():
    with pytest.raises(ExprError, match="entre 0 y 1"):
        quantile(f.x, 1.5)
    with pytest.raises(ExprError, match="un número entre 0 y 1"):
        quantile(f.x, "a")


# --- IQR / mad ----------------------------------------------------------------------

def test_iqr(q):
    assert one(q, IQR(f.x)) == 1.5


def test_iqr_con_na():
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, None]})
    assert one(df, IQR(f.x)) is None
    assert one(df, IQR(f.x, na_rm=True)) == 1.5


def test_mad_constante_de_r():
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 100.0]})
    assert one(df, mad(f.x)) == pytest.approx(1.4826)


def test_mad_center_y_constant():
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 100.0]})
    assert one(df, mad(f.x, center=0, constant=1)) == 3.0
    assert one(df, mad(f.x, constant=1)) == 1.0


def test_mad_con_na():
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0, None]})
    assert one(df, mad(f.x)) is None
    assert one(df, mad(f.x, na_rm=True, constant=1)) == 1.0


def test_resumenes_numericos_rechazan_texto():
    df = pl.DataFrame({"s": ["a", "b"]})
    for expr in (quantile(f.s, 0.5), IQR(f.s), mad(f.s)):
        with pytest.raises(DplyrError, match="necesita un vector numérico"):
            df >> summarise(out=expr)


def test_quantile_en_mutate_reparte_por_grupo():
    df = pl.DataFrame({"g": ["a", "a", "b", "b"], "x": [1.0, 3.0, 10.0, 20.0]})
    out = df >> group_by(f.g) >> mutate(mediana=quantile(f.x, 0.5))
    assert out["mediana"].to_list() == [2.0, 2.0, 15.0, 15.0]
