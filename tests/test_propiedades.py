"""Pruebas aleatorias contra una implementación de referencia en Python puro.

Cada caso genera datos con NA y compara polyr con el cálculo "a mano" de lo
que haría dplyr. Las semillas son fijas para que los fallos sean reproducibles.
"""
import math
import random

import polars as pl
import pytest

from polyr import (arrange, desc, f, filter, group_by, left_join, max, mean, min_rank, mutate,
                   n, summarise, sum)

SEEDS = range(25)


def random_frame(rng: random.Random, n_rows: int) -> pl.DataFrame:
    return pl.DataFrame({
        "g": [rng.choice(["a", "b", "c", None]) for _ in range(n_rows)],
        "x": [rng.choice([None, rng.randint(-5, 5)]) if rng.random() < 0.2 else rng.randint(-5, 5)
              for _ in range(n_rows)],
    }, schema={"g": pl.String, "x": pl.Int64})


def groups_of(df):
    out = {}
    for g, x in zip(df["g"].to_list(), df["x"].to_list()):
        out.setdefault(g, []).append(x)
    return out


def sort_key(value):
    return (value is None, value if value is not None else "")


@pytest.mark.parametrize("seed", SEEDS)
def test_summarise_por_grupo(seed):
    rng = random.Random(seed)
    df = random_frame(rng, rng.randint(0, 30))
    out = df >> group_by(f.g) >> summarise(k=n(), s=sum(f.x), s_rm=sum(f.x, na_rm=True),
                                           m=mean(f.x), mx=max(f.x, na_rm=True))
    expected = []
    for g in sorted(groups_of(df), key=sort_key):
        xs = groups_of(df)[g]
        vals = [v for v in xs if v is not None]
        has_na = len(vals) < len(xs)
        expected.append({
            "g": g, "k": len(xs),
            "s": None if has_na else sum_(vals), "s_rm": sum_(vals),
            "m": None if has_na else sum_(vals) / len(vals),
            "mx": max_(vals) if vals else None,
        })
    assert _close(out.to_dicts(), expected)


def sum_(xs):
    total = 0
    for v in xs:
        total += v
    return total


def max_(xs):
    best = xs[0]
    for v in xs[1:]:
        best = v if v > best else best
    return best


def _close(actual, expected):
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected):
        assert a.keys() == e.keys()
        for k in a:
            if isinstance(e[k], float):
                assert math.isclose(a[k], e[k])
            else:
                assert a[k] == e[k], (k, a, e)
    return True


@pytest.mark.parametrize("seed", SEEDS)
def test_filter_por_grupo_conserva_orden(seed):
    rng = random.Random(seed)
    df = random_frame(rng, rng.randint(0, 30))
    out = df >> group_by(f.g) >> filter(f.x >= mean(f.x, na_rm=True))
    means = {g: (sum_(v) / len(v) if (v := [x for x in xs if x is not None]) else None)
             for g, xs in groups_of(df).items()}
    expected = [(g, x) for g, x in zip(df["g"], df["x"])
                if x is not None and means[g] is not None and x >= means[g]]
    assert list(zip(out["g"], out["x"])) == expected


@pytest.mark.parametrize("seed", SEEDS)
def test_arrange_desc_na_al_final_y_estable(seed):
    rng = random.Random(seed)
    df = random_frame(rng, rng.randint(0, 30)).with_row_index("i")
    out = df >> arrange(desc(f.x))
    rows = list(zip(df["i"], df["x"]))
    expected = sorted(rows, key=lambda r: (r[1] is None, -(r[1] or 0)))
    assert list(zip(out["i"], out["x"])) == expected


@pytest.mark.parametrize("seed", SEEDS)
def test_min_rank(seed):
    rng = random.Random(seed)
    df = random_frame(rng, rng.randint(0, 30))
    out = df >> mutate(r=min_rank(f.x))
    xs = df["x"].to_list()
    expected = [None if x is None else 1 + len([y for y in xs if y is not None and y < x])
                for x in xs]
    assert out["r"].to_list() == expected


@pytest.mark.parametrize("seed", SEEDS)
def test_left_join_contra_referencia(seed):
    rng = random.Random(seed)
    x = random_frame(rng, rng.randint(0, 15)).rename({"x": "vx"})
    y = pl.DataFrame({"g": ["a", "b", None], "vy": [1, 2, 3]})
    out = left_join(x, y, by="g")
    lookup = dict(zip(y["g"], y["vy"]))
    expected = [(g, vx, lookup.get(g)) for g, vx in zip(x["g"], x["vx"])]
    assert list(zip(out["g"], out["vx"], out["vy"])) == expected
