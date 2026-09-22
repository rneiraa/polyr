# Diferencias con dplyr

Lista de todos los puntos donde polyr se comporta distinto que dplyr, y por
qué. **Cualquier diferencia no listada aquí es un bug**: por favor, repórtala.

## Impuestas por Python

| dplyr | polyr | Motivo |
|-------|-------|--------|
| `x` | `f.x` | Python evalúa los argumentos antes de la llamada. |
| `%>%` / `|>` | `>>` | No se pueden definir operadores nuevos. |
| `x > 1 & y < 2` | `(f.x > 1) & (f.y < 2)` | `&` tiene más precedencia que `>` en Python. |
| `&&`, `||`, `!` | `&`, `|`, `~` | `and`/`or`/`not` no se pueden sobrecargar; usarlos da error. |
| `x %in% y` | `is_in(f.x, y)` | No existen operadores `%...%`. |
| `.keep`, `.by`, `.default` | `_keep`, `_by`, `_default` | `.` no es válido en un nombre de argumento. |
| `x = NULL` | `x=None` | `None` es el equivalente de `NULL`. |
| `NA` | `NA` (importado de polyr) | En Python `None` ya significa `NULL`. |
| `%%`, `%/%` | `%`, `//` | Misma semántica (signo del divisor, división hacia abajo). |
| `^` | `**` | Siempre devuelve double, como en R. |
| `a:c` | `f["a":"c"]` | No existe `:` como operador. |
| `!x` en tidyselect | `~f.x` | `!` no existe en Python. |
| `case_when(x ~ v)` | `case_when((f.x, v))` | No existen fórmulas. |
| `mean(x, na.rm = TRUE)` | `mean(f.x, na_rm=True)` | Convención de nombres de Python. |
| `is.na()`, `as.integer()` | `is_na()`, `as_integer()` | `.` no es válido en un nombre. |
| Funciones como `\(x) x * 2` en `across` | `lambda c: c * 2` | La función recibe la **referencia** a la columna. |

## Decisiones de diseño

| Caso | dplyr | polyr | Motivo |
|------|-------|-------|--------|
| Posiciones en `select(1, 3)` | se aceptan | no se aceptan | Ambigüedad base 0 / base 1. |
| `slice(df, 1:3)` | existe | no existe | Misma ambigüedad; usa `slice_head`, `slice_tail`, `slice_min`... |
| `nth(x, 2)` | base 1; negativos desde el final | igual | Decidido: `n` es un argumento del análisis, no un índice de Python. Con base 0, el código portado desde R daría el valor equivocado en silencio. |
| `mutate(x * 2)` sin nombre | nombra la columna `x * 2` | error | Los nombres con código son frágiles. |
| Índices de fila en mensajes de error | base 1 | base 0 | Coinciden con la indexación de Python. |
| `bind_rows(.id)` sin nombres | "1", "2", ... | "1", "2", ... | Se conserva: son etiquetas, no índices. |
| `row_number()`, rankings, `ntile()` | empiezan en 1 | empiezan en 1 | Se conserva: son valores, no índices. |
| `min()`/`max()` de un vector vacío | `Inf`/`-Inf` con advertencia | NA | Un resultado infinito silencioso es peor que NA. |
| `mean()` de texto | NA con advertencia | error | Siguiendo la filosofía estricta de vctrs. |
| `slice_sample()` | generador de R | generador de polars | No es posible reproducir el RNG de R; `seed=` lo hace reproducible. |
| Mensajes (`message()`) | consola | `warnings` con clase `DplyrMessage` | Forma idiomática de Python; se pueden silenciar. |
| Filas con nombre (`rownames`) | no se conservan | no existen | polars no tiene índice de filas. |
| Orden de strings | locale "C" | locale "C" (bytes) | Igual que dplyr ≥ 1.1. |

## Nombres que coinciden con built-ins de Python

`filter`, `sum`, `min`, `max`, `abs` y `round` tienen el nombre de R y por
eso ocultan a los built-ins si se importan. Importa solo lo que uses.

## Aún no implementado

Ver [ROADMAP.md](../ROADMAP.md). Los argumentos que existen pero aún no
funcionan (por ejemplo `keep=True` en los joins) lanzan un error explícito
en lugar de ignorarse en silencio.
