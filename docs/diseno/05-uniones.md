# Diseño: uniones de tablas

**Módulos:** `polyr/joins.py`, `polyr/bind.py`

## Semántica de dplyr 1.1 que se reproduce

| Aspecto | dplyr | polars directo | polyr |
|---------|-------|----------------|-------|
| NA en las claves | coinciden (`na_matches = "na"`) | no coinciden | coinciden; `na_matches="never"` para desactivar |
| Orden de filas | el de `x`; las de `y` sin pareja al final | depende de `maintain_order` | el de `x`; las de `y` sin pareja al final |
| Tipos de claves | tipo común (vctrs) | error o conversión implícita | tipo común; error nombrando `x$col` y `y$col` |
| Columnas repetidas | sufijos `.x` / `.y` | sufijo `_right` | sufijos `.x` / `.y` |
| `by` omitido | columnas en común + mensaje | error | columnas en común + mensaje |
| Varias coincidencias | `multiple = "all"`; advierte muchos-a-muchos | todas | igual que dplyr |

## Algoritmo de las uniones con mutación

1. Resolver las claves (`by=None`, string, lista, diccionario o `join_by()`).
2. Llevar cada par de claves a su tipo común.
3. Aplicar sufijos a las columnas no clave repetidas.
4. Numerar las filas de `x` e `y`.
5. Calcular las coincidencias una vez (`inner`) para validar `relationship`,
   `unmatched` y detectar relaciones muchos-a-muchos.
6. Unir (`right_join` se hace como `full` y se filtra), ordenar por
   (fila de `x`, fila de `y`) con nulos al final, y aplicar `multiple`.

Los índices de fila en los mensajes de error son base 0.

## `bind_rows` y `bind_cols`

* `bind_rows` empareja columnas por nombre, rellena con NA y lleva cada
  columna al tipo común de todas las tablas mediante `cast()` sin pérdida.
* `bind_cols` exige el mismo número de filas (o 1, que se recicla) y repara
  nombres repetidos como vctrs (`a...1`, `a...2`) con un mensaje.

## Pendiente

`join_by()` con desigualdades, `closest()` (rolling), `between()`,
`within()` y `overlaps()`; `keep=True`; `nest_join()`; operaciones de
conjuntos (`union`, `intersect`, `setdiff`, `symdiff`).
