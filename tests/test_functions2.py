import math

import polars as pl
import pytest

from polyr import (NA, between, case_when, cumall, cumany, cummax, cummean, cummin, cume_dist,
                   cumsum, dense_rank, f, first, group_by, lag, last, lead, max, median, min,
                   min_rank, mutate, n_distinct, na_if, near, ntile, percent_rank, row_number,
                   sd, sum, summarise, var)
from polyr.errors import DplyrError

nan = float("nan")


def col(df, expr):
    return (df >> mutate(out=expr))["out"].to_list()


def one(df, expr):
    return (df >> summarise(out=expr))["out"][0]


@pytest.fixture
def df():
    return pl.DataFrame({"x": [3, 1, None, 2], "d": [1.5, nan, 2.0, 4.0],
                         "b": [True, False, True, None], "s": ["b", "a", "c", "a"]})


# --- resúmenes ---------------------------------------------------------------------

def test_sum(df):
    assert one(df, sum(f.x)) is None
    assert one(df, sum(f.x, na_rm=True)) == 6
    assert math.isnan(one(df, sum(f.d)))
    assert one(df, sum(f.d, na_rm=True)) == 7.5
    assert one(df, sum(f.b, na_rm=True)) == 2


def test_sum_vacia_es_cero():
    empty = pl.DataFrame({"x": pl.Series([], dtype=pl.Int64)})
    assert one(empty, sum(f.x)) == 0


def test_min_max(df):
    assert one(df, min(f.x)) is None
    assert one(df, min(f.x, na_rm=True)) == 1
    assert one(df, max(f.x, na_rm=True)) == 3
    assert math.isnan(one(df, max(f.d)))
    assert one(df, max(f.d, na_rm=True)) == 4.0
    assert one(df, min(f.s)) == "a"


def test_median(df):
    assert one(df, median(f.x)) is None
    assert one(df, median(f.x, na_rm=True)) == 2.0
    assert one(df, median(f.d)) is None  # NaN también cuenta como faltante


def test_sd_var():
    d = pl.DataFrame({"x": [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]})
    assert one(d, var(f.x)) == pytest.approx(32 / 7)
    assert one(d, sd(f.x)) == pytest.approx(math.sqrt(32 / 7))
    assert one(pl.DataFrame({"x": [1.0]}), sd(f.x)) is None


def test_first_last(df):
    assert one(df, first(f.x)) == 3
    assert one(df, last(f.x)) == 2
    assert one(df, first(f.b, na_rm=True)) is True
    empty = pl.DataFrame({"x": pl.Series([], dtype=pl.Int64)})
    assert one(empty, first(f.x, default=0)) == 0


def test_n_distinct(df):
    assert one(df, n_distinct(f.s)) == 3
    assert one(df, n_distinct(f.x)) == 4
    assert one(df, n_distinct(f.x, na_rm=True)) == 3
    assert one(df, n_distinct(f.s, f.b)) == 4


def test_resumenes_por_grupo():
    d = pl.DataFrame({"g": ["a", "a", "b"], "x": [1, 2, 10]})
    out = d >> group_by(f.g) >> summarise(s=sum(f.x), mx=max(f.x))
    assert out["s"].to_list() == [3, 10]
    assert out["mx"].to_list() == [2, 10]


# --- case_when y compañía ------------------------------------------------------------

def test_case_when(df):
    out = col(df, case_when((f.x < 2, "bajo"), (f.x < 3, "medio"), _default="alto"))
    assert out == ["alto", "bajo", "alto", "medio"]


def test_case_when_na_es_false():
    d = pl.DataFrame({"b": [True, None, False]})
    assert col(d, case_when((f.b, 1), _default=0)) == [1, 0, 0]


def test_case_when_sin_default_es_na(df):
    assert col(df, case_when((f.x > 2, "alto"))) == ["alto", None, None, None]


def test_case_when_tipo_comun(df):
    out = df >> mutate(out=case_when((f.x > 2, 1), _default=0.5))
    assert out["out"].dtype == pl.Float64


def test_case_when_tipos_incompatibles(df):
    with pytest.raises(DplyrError, match="No se puede combinar"):
        df >> mutate(out=case_when((f.x > 2, 1), _default="no"))


def test_case_when_condicion_no_logica(df):
    with pytest.raises(DplyrError, match="lógico"):
        df >> mutate(out=case_when((f.x, 1)))


def test_na_if(df):
    assert col(df, na_if(f.s, "a")) == ["b", None, "c", None]


def test_between(df):
    assert col(df, between(f.x, 2, 3)) == [True, False, None, True]


def test_near():
    d = pl.DataFrame({"x": [0.1 + 0.2]})
    assert col(d, near(f.x, 0.3)) == [True]


# --- ventana ---------------------------------------------------------------------------

def test_lag_lead(df):
    assert col(df, lag(f.x)) == [None, 3, 1, None]
    assert col(df, lead(f.x, 2)) == [None, 2, None, None]
    assert col(df, lag(f.x, default=0)) == [0, 3, 1, None]


def test_lag_por_grupo():
    d = pl.DataFrame({"g": ["a", "b", "a", "b"], "x": [1, 2, 3, 4]})
    assert (d >> group_by(f.g) >> mutate(p=lag(f.x)))["p"].to_list() == [None, None, 1, 2]


def test_rankings():
    d = pl.DataFrame({"x": [10, 20, 10, None, 30]})
    assert col(d, row_number()) == [1, 2, 3, 4, 5]
    assert col(d, row_number(f.x)) == [1, 3, 2, None, 4]
    assert col(d, min_rank(f.x)) == [1, 3, 1, None, 4]
    assert col(d, dense_rank(f.x)) == [1, 2, 1, None, 3]
    assert col(d, percent_rank(f.x)) == [0.0, 2 / 3, 0.0, None, 1.0]
    assert col(d, cume_dist(f.x)) == [0.5, 0.75, 0.5, None, 1.0]


@pytest.mark.parametrize("n_rows, bins, expected", [
    (10, 3, [1, 1, 1, 1, 2, 2, 2, 3, 3, 3]),
    (5, 2, [1, 1, 1, 2, 2]),
    (3, 5, [1, 2, 3]),
    (6, 3, [1, 1, 2, 2, 3, 3]),
])
def test_ntile_como_dplyr(n_rows, bins, expected):
    d = pl.DataFrame({"x": list(range(n_rows))})
    assert col(d, ntile(f.x, bins)) == expected


def test_ntile_con_na():
    d = pl.DataFrame({"x": [3, None, 1, 2]})
    assert col(d, ntile(f.x, 2)) == [2, None, 1, 1]


def test_acumulados_propagan_na():
    d = pl.DataFrame({"x": [1, 2, None, 4]})
    assert col(d, cumsum(f.x)) == [1, 3, None, None]
    assert col(d, cummean(f.x)) == [1.0, 1.5, None, None]
    assert col(d, cummin(f.x)) == [1, 1, None, None]
    assert col(d, cummax(f.x)) == [1, 2, None, None]


def test_cumall_cumany():
    d = pl.DataFrame({"b": [True, None, False, True]})
    assert col(d, cumall(f.b)) == [True, None, False, False]
    d2 = pl.DataFrame({"b": [False, None, True, False]})
    assert col(d2, cumany(f.b)) == [False, None, True, True]


def test_ventana_con_na_explicito():
    d = pl.DataFrame({"x": [1, 2]})
    assert col(d, lag(f.x, default=NA)) == [None, 1]
