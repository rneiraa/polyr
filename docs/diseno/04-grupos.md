# Diseño: grupos

**Módulos:** `polyr/grouped.py`, `polyr/_core.py`, `polyr/summarise.py`
· **Equivale a:** `grouped_df` de dplyr

## Representación

Un `GroupedFrame` es un `polars.DataFrame` más la lista de columnas de
agrupación. No precalcula índices de grupos (dplyr sí): polars resuelve los
grupos al vuelo con `over()` o `group_by()`, que es rápido y evita que la
estructura quede desincronizada con los datos.

```python
g = df >> group_by(f.tienda)
g.data      # el DataFrame
g.groups    # ["tienda"]
```

Los verbos aceptan tanto `DataFrame` como `GroupedFrame`, y devuelven un
`GroupedFrame` cuando el resultado sigue agrupado.

## Cómo se evalúa cada verbo con grupos

| Verbo | Estrategia | Orden del resultado |
|-------|------------|---------------------|
| `mutate`, `filter` | la expresión compilada se envuelve en `.over(grupos)` | el de las filas originales |
| `summarise` | `group_by(...).agg(...)`, una expresión a la vez | por grupos (ascendente, NA al final) |
| `reframe` | `agg` + validación de tamaños + `explode` | por grupos |
| `slice_*` | ventana con `int_range`/`rank` sobre los grupos | por grupos |
| `arrange` | ignora los grupos, salvo `_by_group=True` | por las claves |
| `select` | agrega las variables de agrupación que falten (con mensaje) | — |

## `summarise` secuencial

dplyr permite `summarise(m = mean(x), d = m * 2)`: `m` es un único valor por
grupo. polyr lo reproduce así:

1. Cada resumen se calcula con `group_by(grupos).agg(expr)`.
2. Se vuelve a unir a los datos de trabajo (con `nulls_equal=True`, porque
   NA es un grupo válido).
3. En las expresiones siguientes, las referencias a resúmenes ya calculados
   se reemplazan por `pl.col(nombre).first()` (clase `_Summary`), de modo que
   valen un escalar por grupo y no una columna repetida.

El tamaño de cada resumen se valida: si en algún grupo no es 1, el error
indica el grupo y sugiere `reframe()`.

## Qué pasa con los grupos después de cada verbo

| Verbo | Grupos del resultado |
|-------|----------------------|
| `filter`, `mutate`, `arrange`, `slice_*`, `distinct`, `select`, `rename`, `relocate` | se conservan (renombrados si corresponde) |
| `summarise` | `_groups`: `"drop_last"` (defecto), `"drop"`, `"keep"` |
| `reframe` | siempre sin grupos |
| `count`, `add_count` | los de la entrada |
| `tally` | se quita el último nivel |
| joins | los de `x` |
| cualquier verbo con `_by` | sin grupos |

Usar `_by` sobre un data frame ya agrupado es un error, como en dplyr.

## Mensajes

Los mensajes informativos de dplyr (`message()`) se emiten como advertencias
de la clase `DplyrMessage`, que se pueden silenciar:

```python
import warnings
from polyr import DplyrMessage
warnings.simplefilter("ignore", DplyrMessage)
```

## Pendiente

`rowwise()`, `cur_group()`, `cur_group_id()`, `cur_group_rows()`,
`group_split()`, `group_map()`, `group_modify()`, grupos vacíos de factores
(`.drop = FALSE`).
