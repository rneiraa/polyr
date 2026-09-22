# Tutorial

Este tutorial recorre polyr con un conjunto de datos pequeño. Cada bloque de
código se ejecuta en los tests (`tests/test_docs.py`), así que siempre está
al día.

## Datos

```python
import polars as pl
from polyr import f

ventas = pl.DataFrame({
    "tienda":   ["Centro", "Centro", "Norte", "Norte", "Norte", "Sur", "Sur", None],
    "producto": ["café", "té", "café", "café", "té", "café", "té", "café"],
    "unidades": [10, 4, 7, None, 3, 12, 5, 2],
    "precio":   [2.5, 3.0, 2.5, 2.5, 3.0, 2.4, float("nan"), 2.5],
})
```

`f.columna` hace referencia a una columna. `f["nombre raro"]` sirve para
nombres que no son identificadores de Python.

## Filtrar filas

```python
from polyr import filter, is_na, is_in

cafe = ventas >> filter(f.producto == "café", f.unidades > 5)
assert cafe["unidades"].to_list() == [10, 7, 12]

# Las filas donde la condición es NA se descartan, como en dplyr:
assert (ventas >> filter(f.unidades > 0)).height == 7

# `%in%` nunca devuelve NA:
assert (ventas >> filter(is_in(f.tienda, ["Norte", "Sur"]))).height == 5
```

Para combinar condiciones usa `&`, `|` y `~`, **siempre con paréntesis**:
`(f.x > 1) & (f.y < 2)`. Usar `and`/`or`/`not` da un error explicativo.

## Crear columnas

```python
from polyr import mutate, if_else, case_when, NA

v = ventas >> mutate(
    total=f.unidades * f.precio,
    grande=if_else(f.total > 20, "sí", "no"),
    tamano=case_when((f.unidades < 5, "chico"), (f.unidades < 10, "mediano"),
                     _default="grande"),
)
assert v["grande"].to_list()[:3] == ["sí", "no", "no"]
```

Las columnas se crean en orden: `grande` usa `total`, creada en el mismo
`mutate`. `columna=None` elimina una columna; `columna=NA` la llena de NA.

## Resumir por grupos

```python
from polyr import group_by, summarise, n, mean, sum

por_tienda = (
    ventas
    >> group_by(f.tienda)
    >> summarise(filas=n(), unidades=sum(f.unidades, na_rm=True),
                 precio_medio=mean(f.precio, na_rm=True))
)
# Los grupos quedan ordenados, con NA al final:
assert por_tienda["tienda"].to_list() == ["Centro", "Norte", "Sur", None]
```

`mean(f.precio)` sin `na_rm=True` daría NA en "Sur", porque tiene un NaN
(en R, `is.na(NaN)` es TRUE). polars, en cambio, ignoraría los nulos en
silencio.

Con varias variables de agrupación, `summarise()` quita la última e informa
el resultado; `_groups="drop"` elimina todos los grupos sin mensaje:

```python
tabla = ventas >> group_by(f.tienda, f.producto) >> summarise(n=n(), _groups="drop")
```

Para agrupar una sola operación sin crear un data frame agrupado, usa `_by`:

```python
m = ventas >> mutate(media_tienda=mean(f.unidades, na_rm=True), _by=f.tienda)
```

## Contar

```python
from polyr import count

conteo = ventas >> count(f.producto, sort=True)
assert conteo.to_dicts() == [{"producto": "café", "n": 5}, {"producto": "té", "n": 3}]
```

## Seleccionar y reordenar columnas

```python
from polyr import select, rename, relocate, starts_with, where, is_numeric

assert (ventas >> select(where(is_numeric))).columns == ["unidades", "precio"]
assert (ventas >> select(-f.precio)).columns == ["tienda", "producto", "unidades"]
assert (ventas >> select(f["producto":"precio"])).columns == ["producto", "unidades", "precio"]
assert (ventas >> rename(local=f.tienda)).columns[0] == "local"
assert (ventas >> relocate(f.precio, _after=f.tienda)).columns[1] == "precio"
```

## Ordenar

```python
from polyr import arrange, desc

o = ventas >> arrange(desc(f.unidades))
# NA siempre al final, también en orden descendente:
assert o["unidades"].to_list()[-1] is None
```

## Varias columnas a la vez: `across()`

```python
from polyr import across

medias = ventas >> group_by(f.producto) >> summarise(
    across(where(is_numeric), lambda c: mean(c, na_rm=True)))
assert medias.columns == ["producto", "unidades", "precio"]
```

## Funciones de ventana

```python
from polyr import lag, min_rank, cumsum

r = (ventas
     >> group_by(f.tienda)
     >> mutate(anterior=lag(f.unidades), ranking=min_rank(desc(f.unidades))))
```

Con grupos, las funciones de ventana trabajan dentro de cada grupo.

## Unir tablas

```python
from polyr import left_join, join_by

tiendas = pl.DataFrame({"nombre": ["Centro", "Norte", "Sur"],
                        "region": ["RM", "RM", "Biobío"]})
con_region = ventas >> left_join(tiendas, by=join_by(f.tienda == f.nombre))
assert con_region.height == ventas.height
assert con_region.columns[-1] == "region"
```

Las uniones conservan el orden de las filas de `x`, llevan las claves a su
tipo común y, como en dplyr, consideran que NA coincide con NA
(`na_matches="never"` lo desactiva).

## Errores

Los errores dicen qué verbo y qué argumento fallaron:

```python
from polyr import DplyrError

try:
    ventas >> mutate(total=f.unidades * f.precioo)
except DplyrError as err:
    assert "`precioo`" in str(err)
```
