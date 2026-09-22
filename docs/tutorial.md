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

`lag()` y `lead()` aceptan `order_by=` para seguir otro orden sin reordenar
las filas, y `nth()` elige una posición concreta (contando desde 1, como en
R; `-1` es la última):

```python
from polyr import lead, nth, consecutive_id

r = (ventas
     >> group_by(f.tienda)
     >> mutate(siguiente=lead(f.unidades, order_by=f.producto),
               tramo=consecutive_id(f.producto)))

ultimas = ventas >> group_by(f.tienda) >> summarise(ultima=nth(f.unidades, -1))
```

## Recodificar valores: `case_match()`

Cuando la condición es siempre "¿está entre estos valores?", `case_match()`
dice lo mismo que `case_when()` con menos ruido:

```python
from polyr import case_match

etiquetadas = ventas >> mutate(
    zona=case_match(f.tienda, (["Centro", "Norte"], "capital"), ("Sur", "regiones"),
                    _default="sin dato"))
assert etiquetadas["zona"].to_list()[-1] == "sin dato"   # la tienda NA
```

## Varias columnas como un valor: `pick()`

`across()` aplica una función a cada columna por separado; `pick()` entrega
varias columnas **juntas** a una función que las necesita a la vez:

```python
from polyr import dense_rank, n_distinct, pick

combinaciones = ventas >> summarise(pares=n_distinct(pick(f.tienda, f.producto)))
ordenadas = ventas >> mutate(orden=dense_rank(pick(f.producto, f.unidades)))
assert combinaciones["pares"][0] == 7
# La fila sin unidades queda sin ranking, como en dplyr:
assert ordenadas["orden"][3] is None
```

## Cuantiles

`quantile()` usa la interpolación lineal que R trae por defecto (`type = 7`).
A diferencia de R, hay que decir qué cuantil se quiere:

```python
from polyr import IQR, quantile, reframe

resumen = ventas >> group_by(f.producto) >> summarise(
    mediana=quantile(f.unidades, 0.5, na_rm=True),
    rango=IQR(f.unidades, na_rm=True))

# Con varios cuantiles el resultado tiene varias filas, así que va en reframe():
cuartiles = ventas >> reframe(q=quantile(f.unidades, [0.25, 0.5, 0.75], na_rm=True))
assert cuartiles.height == 3
```

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

### Unir por rango y por cercanía

`join_by()` no se limita a la igualdad. Puede comparar columnas con `>=`,
`>`, `<=` y `<`, y tiene tres formas de escribir un rango: `between()`,
`within()` y `overlaps()`.

```python
from polyr import between, closest, inner_join, row_number

tarifas = pl.DataFrame({"tienda": ["Centro", "Centro", "Norte", "Sur"],
                        "desde":  [1, 6, 1, 1],
                        "hasta":  [5, 10, 10, 10],
                        "tasa":   [0.10, 0.20, 0.15, 0.05]})
dias = ventas >> mutate(dia=row_number())

con_tarifa = dias >> inner_join(
    tarifas, by=join_by(f.tienda, between(f.dia, f.desde, f.hasta)))
assert "tasa" in con_tarifa.columns
```

`closest()` se queda solo con la pareja más cercana. Es la unión rodante que
en R se escribe igual:

```python
cortes = pl.DataFrame({"corte": [0, 5, 10], "tramo": ["bajo", "medio", "alto"]})
tramos = dias >> left_join(cortes, by=join_by(closest(f.dia >= f.corte)))
assert tramos["tramo"].to_list()[:3] == ["bajo", "bajo", "bajo"]
```

Una unión por desigualdad conserva las columnas comparadas de las dos
tablas, porque ningún valor único puede representarlas.

## Operaciones de conjuntos

Cuando las dos tablas tienen las mismas columnas, cada fila se puede tratar
como un elemento de un conjunto:

```python
from polyr import intersect, setdiff, union

a = pl.DataFrame({"x": [1, 2, 2, 3]})
b = pl.DataFrame({"x": [2, 4]})

assert union(a, b)["x"].to_list() == [1, 2, 3, 4]
assert intersect(a, b)["x"].to_list() == [2]
assert setdiff(a, b)["x"].to_list() == [1, 3]
```

Todas salvo `union_all()` devuelven filas únicas, y NA cuenta como igual a NA.

## Errores

Los errores dicen qué verbo y qué argumento fallaron:

```python
from polyr import DplyrError

try:
    ventas >> mutate(total=f.unidades * f.precioo)
except DplyrError as err:
    assert "`precioo`" in str(err)
```
