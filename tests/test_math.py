import math

import polars as pl

from polyr import (NA, abs, as_character, as_double, as_integer, as_logical, ceiling, f,
                   filter, floor, is_in, log, log10, mutate, pmax, pmin, round, sqrt)


def col(df, expr):
    return (df >> mutate(out=expr))["out"].to_list()


def test_is_in_nunca_devuelve_na():
    d = pl.DataFrame({"x": ["a", "b", None]})
    assert col(d, is_in(f.x, ["a"])) == [True, False, False]
    assert col(d, is_in(f.x, ["a", None])) == [True, False, True]


def test_is_in_en_filter():
    d = pl.DataFrame({"x": [1, 2, 3]})
    assert (d >> filter(is_in(f.x, [1, 3])))["x"].to_list() == [1, 3]
    assert (d >> filter(~is_in(f.x, [1, 3])))["x"].to_list() == [2]


def test_is_in_con_tipos_compatibles():
    d = pl.DataFrame({"x": [1, 2]})
    assert col(d, is_in(f.x, [2.0])) == [False, True]


def test_round_mitad_al_par_como_r():
    d = pl.DataFrame({"x": [0.5, 1.5, 2.5, -0.5, 1.234]})
    assert col(d, round(f.x)) == [0.0, 2.0, 2.0, -0.0, 1.0]
    assert col(d, round(f.x, 2))[-1] == 1.23


def test_math_basica():
    d = pl.DataFrame({"x": [-4, 4, None]})
    assert col(d, abs(f.x)) == [4, 4, None]
    assert math.isnan(col(d, sqrt(f.x))[0])
    assert col(d, sqrt(f.x))[1] == 2.0
    assert col(pl.DataFrame({"x": [100.0]}), log10(f.x)) == [2.0]
    assert col(pl.DataFrame({"x": [8.0]}), log(f.x, base=2)) == [3.0]
    assert col(pl.DataFrame({"x": [1.5]}), floor(f.x)) == [1.0]
    assert col(pl.DataFrame({"x": [1.5]}), ceiling(f.x)) == [2.0]


def test_pmin_pmax():
    d = pl.DataFrame({"a": [1, 5, None], "b": [3, 2, 4]})
    assert col(d, pmin(f.a, f.b)) == [1, 2, None]
    assert col(d, pmax(f.a, f.b, na_rm=True)) == [3, 5, 4]
    assert col(d, pmax(f.a, 0)) == [1, 5, None]


def test_conversiones_como_r():
    d = pl.DataFrame({"x": [2.7, -2.7, None], "s": ["1", "a", "3.9"],
                      "b": [True, False, None], "t": ["TRUE", "f", "si"]})
    assert col(d, as_integer(f.x)) == [2, -2, None]
    assert col(d, as_integer(f.s)) == [1, None, 3]
    assert col(d, as_double(f.s)) == [1.0, None, 3.9]
    assert col(d, as_character(f.b)) == ["TRUE", "FALSE", None]
    assert col(d, as_logical(f.t)) == [True, False, None]


def test_na_se_propaga():
    d = pl.DataFrame({"x": [1.0]})
    assert col(d, abs(NA)) == [None]
