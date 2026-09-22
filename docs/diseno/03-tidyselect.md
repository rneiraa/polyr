# Diseño: tidyselect

**Módulo:** `polyr/tidyselect.py` · **Equivale a:** tidyselect

## Idea

Una selección usa los mismos nodos que cualquier expresión, pero se
**resuelve** a una lista ordenada de nombres en lugar de compilarse a
polars. Así `-f.x` significa "negar x" en `mutate` y "excluir x" en `select`,
igual que en R.

## Sintaxis

| R                    | polyr                  |
|----------------------|----------------------|
| `x`, `"x"`           | `f.x`, `"x"`         |
| `a:c`                | `f["a":"c"]`         |
| `-x`                 | `-f.x`               |
| `!x`                 | `~f.x`               |
| `a | b`, `a & b`     | `a | b`, `a & b`     |
| `c("a", "b")`        | `["a", "b"]`         |
| `nuevo = x`          | `nuevo=f.x`          |

## Reglas de evaluación

1. Los argumentos se procesan en orden; el resultado conserva el orden de
   primera aparición y no repite columnas.
2. `-sel` elimina columnas de lo acumulado. Si es el **primer** argumento,
   se parte de todas las columnas (`select(-f.id)` = todo menos `id`).
3. `~sel` es el complemento respecto de todas las columnas.
4. Los renombres (`nuevo=f.x`) se aplican al final; si la columna ya estaba
   seleccionada conserva su posición.
5. Los nombres finales deben ser únicos.
6. Una columna inexistente es error, salvo con `any_of()`.

## Helpers

| Helper                  | Nota                                          |
|-------------------------|-----------------------------------------------|
| `starts_with`, `ends_with`, `contains` | `ignore_case=True` por defecto, como en R |
| `matches`               | expresión regular, `ignore_case=True`         |
| `num_range`             | `num_range("x", range(1, 4), width=2)`        |
| `everything`, `last_col`| `last_col(offset)`                            |
| `all_of`, `any_of`      | estricto / permisivo con faltantes            |
| `where`                 | predicado sobre la Series: `where(is_numeric)`|

Un selector usado fuera de un contexto de selección (p. ej. en `mutate`) da
un error explicativo.

## Decisión: sin posiciones numéricas

tidyselect acepta `select(1, 3)`. polyr **no**, a propósito: en Python las
posiciones empiezan en 0 y en R en 1, y cualquiera de las dos elecciones
produciría errores silenciosos para la mitad de los usuarios. Se usan nombres,
rangos por nombre o `last_col()`.
