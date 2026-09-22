"""`lag()` y `lead()` con `order_by=`: desplazar siguiendo otro orden."""
import polars as pl

from polyr import f, group_by, lag, lead, mutate


def prev(d, **kwargs):
    return (d >> mutate(out=lag(f.valor, **kwargs)))["out"].to_list()


def desordenada():
    return pl.DataFrame({"anio": [2022, 2020, 2021], "valor": [30, 10, 20]})


def test_lag_order_by_sigue_el_orden_pedido():
    d = desordenada()  # ordenado por año: 10, 20, 30
    assert prev(d, order_by=f.anio) == [20, None, 10]
    assert (d >> mutate(sig=lead(f.valor, order_by=f.anio)))["sig"].to_list() == [None, 20, 30]


def test_lag_order_by_no_reordena_las_filas():
    out = desordenada() >> mutate(previo=lag(f.valor, order_by=f.anio))
    assert out["anio"].to_list() == [2022, 2020, 2021]


def test_lag_order_by_con_default_y_n():
    assert prev(desordenada(), n=2, default=0, order_by=f.anio) == [10, 0, 0]


def test_lag_order_by_por_grupo():
    d = pl.DataFrame({"g": ["a", "a", "b", "b"], "t": [2, 1, 2, 1], "x": [20, 10, 200, 100]})
    out = d >> group_by(f.g) >> mutate(previo=lag(f.x, order_by=f.t))
    assert out["previo"].to_list() == [10, None, 100, None]


def test_lag_order_by_empates_conservan_el_orden_de_las_filas():
    d = pl.DataFrame({"t": [1, 1, 1], "valor": [1, 2, 3]})
    assert prev(d, order_by=f.t) == [None, 1, 2]


def test_lag_sin_order_by_sigue_el_orden_de_las_filas():
    assert prev(desordenada()) == [None, 30, 10]


def test_lag_order_by_con_grupos_de_distinto_tamano_y_clave_nula():
    d = pl.DataFrame({
        "g": ["C", "C", "N", "N", "N", "S", "S", None],
        "t": ["a", "b", "a", "a", "b", "a", "b", "a"],
        "valor": [10, 4, 7, None, 3, 12, 5, 2],
    })
    out = d >> group_by(f.g) >> mutate(sig=lead(f.valor, order_by=f.t))
    assert out["sig"].to_list() == [4, None, None, 3, None, 5, None, None]


def test_lag_order_by_con_default_en_cada_grupo():
    d = pl.DataFrame({"g": ["a", "a", "b", "b", "b"], "t": [2, 1, 3, 1, 2],
                      "valor": [20, 10, 300, 100, 200]})
    out = d >> group_by(f.g) >> mutate(previo=lag(f.valor, default=0, order_by=f.t))
    assert out["previo"].to_list() == [10, 0, 200, 0, 100]


def test_lag_order_by_con_na_en_la_columna_de_orden():
    d = pl.DataFrame({"t": [2, None, 1], "valor": [20, 99, 10]})
    previo = prev(d, order_by=f.t)
    assert len(previo) == 3 and previo.count(None) == 1   # solo el primero del orden


def test_lag_order_by_es_estable_entre_ejecuciones():
    d = pl.DataFrame({"g": ["a"] * 3 + ["b"] * 5, "t": [1, 1, 1, 2, 2, 1, 1, 3],
                      "valor": list(range(8))})
    resultados = {tuple((d >> group_by(f.g) >> mutate(p=lag(f.valor, order_by=f.t)))["p"])
                  for _ in range(25)}
    assert len(resultados) == 1
