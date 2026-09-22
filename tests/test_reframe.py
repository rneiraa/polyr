import polars as pl
import pytest

from polyr import f, group_by, mean, reframe, summarise
from polyr.errors import DplyrError
from polyr.functions import Call


def quantiles(x):
    """Dos cuantiles por grupo: un resultado de tamaño 2."""
    return Call("quantiles", lambda ctx, e: pl.concat([e.min(), e.max()]), [x])


@pytest.fixture
def df():
    return pl.DataFrame({"g": ["b", "a", "b", "a"], "x": [1, 2, 3, 4]})


def test_reframe_varias_filas_por_grupo(df):
    out = df >> group_by(f.g) >> reframe(q=quantiles(f.x))
    assert out.to_dict(as_series=False) == {"g": ["a", "a", "b", "b"], "q": [2, 4, 1, 3]}
    assert isinstance(out, pl.DataFrame)


def test_reframe_recicla_tamano_1(df):
    out = df >> group_by(f.g) >> reframe(q=quantiles(f.x), m=mean(f.x))
    assert out["m"].to_list() == [3.0, 3.0, 2.0, 2.0]


def test_reframe_sin_grupos(df):
    assert (df >> reframe(y=f.x * 10))["y"].to_list() == [10, 20, 30, 40]


def test_reframe_tamanos_incompatibles(df):
    with pytest.raises(DplyrError, match="o 1, no"):
        pl.DataFrame({"g": ["a"] * 3, "x": [1, 2, 3]}) >> group_by(f.g) >> reframe(
            a=f.x, b=quantiles(f.x))


def test_summarise_sugiere_reframe(df):
    with pytest.raises(DplyrError, match="reframe"):
        df >> group_by(f.g) >> summarise(y=f.x)


def test_reframe_grupo_sin_filas_no_aporta():
    df = pl.DataFrame({"g": ["a", "a", "b"], "x": [1, 5, 2]})
    out = df >> group_by(f.g) >> reframe(y=_above(f.x))
    assert out["g"].to_list() == ["a"]


def _above(x):
    return Call("above", lambda ctx, e: e.filter(e > 3), [x])
