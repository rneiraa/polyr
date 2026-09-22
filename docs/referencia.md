# Referencia de la API

<!-- Archivo generado por scripts/gen_reference.py. No editar a mano. -->

Versión 0.2.0b1. Todo se importa desde `polyr`. Los verbos aceptan llamada directa (`verbo(df, ...)`) o pipe (`df >> verbo(...)`).

## Expresiones y estructuras

| Nombre | Descripción |
|--------|-------------|
| `f.columna` | Referencia a una columna. También `f["nombre"]` y rangos `f["a":"c"]`. |
| `NA` | Valor faltante (`mutate(x=NA)`); `None` equivale a `NULL`. |
| `Expr` | Nodo base del árbol de expresiones. |
| `GroupedFrame` | Data frame con grupos. Se crea con `group_by`. |
| `DplyrError` | Error de un verbo, indicando en qué argumento ocurrió. |
| `DplyrMessage` | Mensaje informativo (el equivalente de `message()` en dplyr). |

## Verbos de una tabla

| Nombre | Descripción |
|--------|-------------|
| `filter(data, /, *conditions, _by=None, **named)` | Conserva las filas donde todas las condiciones son TRUE. |
| `mutate(data, /, *args, _keep="all", _before=None, _after=None, _by=None, **new_columns)` | Crea, modifica o elimina columnas. |
| `select(data, /, *args, **named)` | Selecciona (y opcionalmente renombra) columnas con tidyselect. |
| `rename(data, /, *args, **named)` | Renombra columnas sin cambiar el resto: `rename(df, nuevo=f.viejo)`. |
| `rename_with(data, /, fn, cols=None)` | Renombra con una función: `rename_with(df, str.upper, starts_with("x"))`. |
| `relocate(data, /, *args, _before=None, _after=None, **named)` | Cambia la posición de columnas (por defecto, al principio). |
| `arrange(data, /, *keys, _by_group=False, **named)` | Ordena filas por una o más claves; `desc()` para orden descendente. |
| `pull(data, /, var=None)` | Extrae una columna como Series. Por defecto, la última (como dplyr). |
| `distinct(data, /, *args, _keep_all=False, **named)` | Filas únicas (la primera aparición de cada combinación). |
| `summarise(data, /, *args, _by=None, _groups=None, **named)` | Resume cada grupo a una fila. |
| `reframe(data, /, *args, _by=None, **named)` | Como `summarise()`, pero cada grupo puede producir cualquier número de filas. |
| `count(data, /, *args, wt=None, sort=False, name=None, **named)` | Cuenta filas por combinación de valores: `count(df, f.a, f.b)`. |
| `tally(data, /, wt=None, sort=False, name=None)` | Cuenta filas por grupo (`count()` sin columnas adicionales). |
| `add_count(data, /, *args, wt=None, sort=False, name=None, **named)` | Como `count()`, pero agrega el conteo como columna sin resumir filas. |

## Filas por posición

| Nombre | Descripción |
|--------|-------------|
| `slice_head(data, /, n=None, prop=None, _by=None)` | Primeras `n` filas (o proporción `prop`) de cada grupo. |
| `slice_tail(data, /, n=None, prop=None, _by=None)` | Últimas `n` filas (o proporción `prop`) de cada grupo. |
| `slice_min(data, /, order_by, n=None, prop=None, with_ties=True, na_rm=False, _by=None)` | Filas con los menores valores de `order_by` en cada grupo. |
| `slice_max(data, /, order_by, n=None, prop=None, with_ties=True, na_rm=False, _by=None)` | Filas con los mayores valores de `order_by` en cada grupo. |
| `slice_sample(data, /, n=None, prop=None, replace=False, weight_by=None, seed=None, _by=None)` | Muestra aleatoria de filas por grupo. `seed` la hace reproducible. |

## Grupos

| Nombre | Descripción |
|--------|-------------|
| `group_by(data, /, *args, _add=False, **named)` | Agrupa por columnas existentes o calculadas: `group_by(df, f.a, grande=f.x > 10)`. |
| `ungroup(data, /, *args)` | Quita todos los grupos, o solo los seleccionados: `ungroup(df, f.a)`. |
| `group_vars(data)` | Nombres de las variables de agrupación (lista vacía si no hay grupos). |
| `n_groups(data)` | Número de grupos (1 si no hay grupos). |
| `group_keys(data)` | Una fila por grupo, en el orden de dplyr. |

## Dos tablas

| Nombre | Descripción |
|--------|-------------|
| `inner_join(x, y, /, by=None, suffix=(".x", ".y"), multiple="all", unmatched="drop", relationship=None, na_matches="na", keep=None)` | Filas de `x` con pareja en `y`. |
| `left_join(x, y, /, by=None, suffix=(".x", ".y"), multiple="all", unmatched="drop", relationship=None, na_matches="na", keep=None)` | Todas las filas de `x`; columnas de `y` donde hay pareja. |
| `right_join(x, y, /, by=None, suffix=(".x", ".y"), multiple="all", unmatched="drop", relationship=None, na_matches="na", keep=None)` | Todas las filas de `y`; las que no tienen pareja en `x` van al final. |
| `full_join(x, y, /, by=None, suffix=(".x", ".y"), multiple="all", unmatched="drop", relationship=None, na_matches="na", keep=None)` | Todas las filas de `x` y de `y`. |
| `semi_join(x, y, /, by=None, na_matches="na")` | Filas de `x` que tienen pareja en `y` (sin duplicar ni agregar columnas). |
| `anti_join(x, y, /, by=None, na_matches="na")` | Filas de `x` que **no** tienen pareja en `y`. |
| `cross_join(x, y, /, suffix=(".x", ".y"))` | Todas las combinaciones de filas de `x` e `y`. |
| `join_by(*conditions)` | Claves de unión, como `dplyr::join_by()`. |
| `bind_rows(*frames, _id=None)` | Apila tablas por filas, emparejando columnas por nombre. |
| `bind_cols(*frames)` | Une tablas lado a lado. Todas deben tener el mismo número de filas (o 1, que se recicla). |

## Resúmenes

| Nombre | Descripción |
|--------|-------------|
| `mean(x, na_rm=False)` | Media aritmética, como `mean()` de R. |
| `sum(x, na_rm=False)` | Suma. Con NA y `na_rm=False` es NA; la suma vacía es 0. |
| `min(x, na_rm=False)` | Mínimo. Con NA y `na_rm=False` es NA; NaN se propaga. |
| `max(x, na_rm=False)` | Máximo. Mismas reglas que `min`. |
| `median(x, na_rm=False)` | Mediana. Con algún NA o NaN y `na_rm=False` es NA. |
| `sd(x, na_rm=False)` | Desviación estándar muestral (denominador n - 1). NA con menos de 2 valores. |
| `var(x, na_rm=False)` | Varianza muestral (denominador n - 1). NA con menos de 2 valores. |
| `quantile(x, probs, na_rm=False)` | Cuantil muestral con interpolación lineal (el `type = 7` de R, su defecto). |
| `IQR(x, na_rm=False)` | Rango intercuartílico: el cuantil 0.75 menos el 0.25 (`type = 7`). |
| `mad(x, center=None, constant=1.4826, na_rm=False)` | Desviación absoluta mediana: `constant * median(\|x - center\|)`. |
| `any(x, na_rm=False)` | ¿Hay algún TRUE? Con la lógica de tres valores de R. |
| `all(x, na_rm=False)` | ¿Son todos TRUE? Con la lógica de tres valores de R. |
| `first(x, default=None, na_rm=False)` | Primer valor (`default` si no hay ninguno). |
| `last(x, default=None, na_rm=False)` | Último valor (`default` si no hay ninguno). |
| `n_distinct(*xs, na_rm=False)` | Número de valores (o combinaciones) distintos. NA cuenta como un valor, salvo con `na_rm=True`. |
| `n()` | Número de filas del grupo actual (sin grupos: de la tabla). |

## Condicionales y faltantes

| Nombre | Descripción |
|--------|-------------|
| `is_na(x)` | TRUE donde hay un valor faltante. Como en R, `is_na(NaN)` es TRUE. |
| `if_else(condition, true, false, missing=None)` | Condicional vectorizado y estricto con los tipos, como `dplyr::if_else()`. |
| `case_when(*cases, _default=None)` | Condicional múltiple, como `dplyr::case_when()`. |
| `case_match(x, *cases, _default=None)` | Recodifica valores, como `dplyr::case_match()`. |
| `coalesce(*values)` | Primer valor no faltante de cada posición, como `dplyr::coalesce()`. |
| `na_if(x, y)` | Convierte en NA los valores de `x` iguales a `y`. Conserva el tipo de `x`. |
| `between(x, left, right)` | `left <= x <= right` (inclusivo). NA si alguno es NA. |
| `near(x, y, tol=1.4901161193847656e-08)` | Igualdad con tolerancia para dobles (por defecto `sqrt(eps)`, como R). |

## Ventana

| Nombre | Descripción |
|--------|-------------|
| `lag(x, n=1, default=None)` | Valor `n` filas antes (`default` al principio, NA por defecto). |
| `lead(x, n=1, default=None)` | Valor `n` filas después (`default` al final, NA por defecto). |
| `row_number(x=None)` | Sin argumentos: 1, 2, ..., n. Con `x`: ranking con empates por orden de aparición. |
| `min_rank(x)` | Ranking con huecos (empates reciben el menor rango): 1, 1, 3. |
| `dense_rank(x)` | Ranking sin huecos: 1, 1, 2. |
| `percent_rank(x)` | `(min_rank - 1) / (n - 1)`, con n = número de valores no NA. |
| `cume_dist(x)` | Proporción de valores menores o iguales: `max_rank / n`. |
| `ntile(x, n)` | Divide en `n` grupos lo más parejos posible (los primeros, más grandes). |
| `consecutive_id(*xs)` | Identificador de tramos consecutivos, como `dplyr::consecutive_id()`. |
| `cumsum(x)` | Suma acumulada; desde el primer NA, todo es NA (como en R). |
| `cummean(x)` | Media acumulada; desde el primer NA, todo es NA. |
| `cummin(x)` | Mínimo acumulado; desde el primer NA, todo es NA. |
| `cummax(x)` | Máximo acumulado; desde el primer NA, todo es NA. |
| `cumall(x)` | TRUE mientras todos los valores hasta aquí sean TRUE (una vez FALSE, siempre FALSE). |
| `cumany(x)` | TRUE desde el primer TRUE en adelante. |
| `desc(x)` | Ordena en forma descendente dentro de `arrange()`. |

## Varias columnas

| Nombre | Descripción |
|--------|-------------|
| `across(cols=None, fns=None, names=None)` | Aplica `fns` a cada columna de `cols` (por defecto, todas). |
| `if_any(cols, fn)` | TRUE si `fn` es TRUE para **alguna** columna seleccionada (lógica de NA de R). |
| `if_all(cols, fn)` | TRUE si `fn` es TRUE para **todas** las columnas seleccionadas. |

## Funciones de base R

| Nombre | Descripción |
|--------|-------------|
| `is_in(x, values)` | `x %in% values`. **Nunca devuelve NA**: `NA %in% c(1, NA)` es TRUE y `NA %in% c(1)` es FALSE, como en R (polars devolvería nulo). |
| `abs(x)` | Valor absoluto. |
| `sqrt(x)` | Raíz cuadrada (NaN para negativos, como R). |
| `exp(x)` | Exponencial. |
| `log(x, base=2.718281828459045)` | Logaritmo (natural por defecto). `log(0)` es `-Inf`; negativos dan NaN. |
| `log2(x)` | Logaritmo en base 2. |
| `log10(x)` | Logaritmo en base 10. |
| `floor(x)` | Redondeo hacia abajo (devuelve double, como R). |
| `ceiling(x)` | Redondeo hacia arriba (devuelve double). |
| `round(x, digits=0)` | Redondeo con la regla de R (IEC 60559, "mitad al par"): `round(2.5)` es 2. |
| `pmin(*xs, na_rm=False)` | Mínimo elemento a elemento. NA si alguno es NA, salvo `na_rm=True`. |
| `pmax(*xs, na_rm=False)` | Máximo elemento a elemento. NA si alguno es NA, salvo `na_rm=True`. |
| `as_integer(x)` | Convierte a entero. Los dobles se truncan hacia cero; lo no convertible es NA. |
| `as_double(x)` | Convierte a double; lo no convertible es NA. |
| `as_character(x)` | Convierte a texto. Los lógicos se escriben TRUE/FALSE, como en R. |
| `as_logical(x)` | Convierte a lógico. Acepta "TRUE"/"T"/"FALSE"/"F" (sin importar mayúsculas). |

## Selectores (tidyselect)

| Nombre | Descripción |
|--------|-------------|
| `starts_with(*match, ignore_case=True)` | Columnas cuyo nombre empieza con alguno de los prefijos. |
| `ends_with(*match, ignore_case=True)` | Columnas cuyo nombre termina con alguno de los sufijos. |
| `contains(*match, ignore_case=True)` | Columnas cuyo nombre contiene alguno de los textos (literales). |
| `matches(pattern, ignore_case=True)` | Columnas cuyo nombre coincide con la expresión regular. |
| `num_range(prefix, range, suffix="", width=None)` | Columnas como `x1, x2, x3` (`width` rellena con ceros: `x01`). |
| `everything()` | Todas las columnas. |
| `last_col(offset=0)` | La última columna (`offset=1` es la penúltima, etc.). |
| `all_of(names)` | Columnas nombradas en un vector; **todas** deben existir. |
| `any_of(names)` | Columnas nombradas en un vector; las que no existen se ignoran. |
| `where(predicate)` | Columnas para las que `predicate(serie)` es `True`. |

## Predicados de tipo (para `where`)

| Nombre | Descripción |
|--------|-------------|
| `is_numeric(s)` | Como `is.numeric()`: enteros y dobles (los lógicos no cuentan). |
| `is_integer(s)` | Como `is.integer()`: columnas de enteros. |
| `is_double(s)` | Como `is.double()`: columnas de dobles. |
| `is_character(s)` | Como `is.character()`: columnas de texto. |
| `is_logical(s)` | Como `is.logical()`: columnas lógicas. |

`summarize` es un alias de `summarise`.
