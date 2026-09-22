# Diseño: sistema de expresiones

**Módulo:** `polyr/expr.py` · **Equivale a:** rlang (tidy evaluation)

## El problema

En R, `filter(df, x > 1)` funciona porque los argumentos se evalúan de forma
perezosa: dplyr captura `x > 1` como código y lo evalúa después dentro del
data frame. Python evalúa los argumentos antes de llamar a la función, así que
`x` tendría que existir como variable.

## La solución: `f.x`

`f` es un espacio de nombres cuyos atributos son referencias a columnas.
Los operadores de Python están sobrecargados para que `f.x > 1` construya un
árbol en lugar de calcular un valor:

```
f.x > mean(f.x)   →   BinOp(">", Col("x"), Call("mean", [Col("x")]))
```

| Nodo      | Representa                                   |
|-----------|----------------------------------------------|
| `Col`     | una columna de la data mask                  |
| `Lit`     | un escalar (`1`, `"a"`, `NA`)                |
| `Values`  | un vector constante (lista o Series)         |
| `BinOp`   | operador binario (`+`, `>`, `&`...)          |
| `UnaryOp` | `-x`, `~x`                                   |
| `Call`    | función del paquete (`mean`, `if_else`...)   |
| `Desc`    | marca de orden descendente                   |
| `Between` | `between()`; `join_by()` lo lee como rango   |
| `Selector`| helper de tidyselect (ver 03-tidyselect.md)  |

## Compilación con tipos

Cada nodo implementa `to_polars(ctx) -> pl.Expr`. El `EvalContext` permite
preguntar el tipo de cualquier subexpresión **sin evaluar datos**
(`ctx.dtype(expr)`, que usa `LazyFrame.collect_schema`). Así, `if_else` puede
calcular el tipo común de sus ramas y fallar *antes* de ejecutar si son
incompatibles.

El contexto lleva además el data frame completo y las variables de
agrupación, que necesitan los helpers que resuelven una selección al compilar:
`if_any()`, `if_all()` y `pick()`. Los tres excluyen las variables de
agrupación de su selección, igual que `across()`, porque dentro de un grupo
son constantes.

## Data mask y entorno

Las variables de Python se evalúan al construir la expresión:

```python
limite = 3
filter(df, f.x > limite)   # limite ya vale 3 dentro del árbol
```

Por eso no existe la ambigüedad de R entre columnas y variables (que obliga a
usar `.data$x` / `.env$x`): **las columnas siempre llevan `f.`**.

## Flujo de un verbo

1. `wrap()` convierte cada argumento en un nodo.
2. `columns()` obtiene las columnas referenciadas; si falta alguna, error
   inmediato con el nombre de la columna.
3. `to_polars(ctx)` compila, aplicando las reglas de tipos.
4. Con grupos, la expresión compilada se envuelve en `.over(grupos)`; en
   `summarise` se usa `group_by().agg()` (ver 04-grupos.md).
5. Se evalúa con `DataFrame.select` y se valida tamaño (reciclado) y tipo.
6. Cualquier `ExprError` o error de polars se envuelve en `DplyrError` con el
   verbo y el argumento, en el formato de dplyr.

## Limitaciones de Python y cómo se manejan

| Limitación                              | Manejo                                           |
|-----------------------------------------|--------------------------------------------------|
| `and`/`or`/`not` no se pueden sobrecargar | `__bool__` lanza un error explicando `&`, `|`, `~` |
| `1 < f.x < 5` llama a `__bool__`         | el mismo error lo explica                         |
| `&` tiene más precedencia que `>`        | se documenta; `filter` acepta varias condiciones  |
| `==` sobrecargado impide usar `Expr` como clave | `__hash__ = None` explícito                |

## Pendiente
* Evaluación perezosa de toda la tubería (hoy cada argumento se evalúa por
  separado, lo que es correcto pero no óptimo).
* Pronombres `.data`/`.env` para programar funciones que reciban nombres.
