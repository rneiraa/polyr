# Diseño: uniones y combinación de tablas

**Módulos:** `polyr/joins.py`, `polyr/bind.py`, `polyr/sets.py`

## Semántica de dplyr 1.1 que se reproduce

| Aspecto | dplyr | polars directo | polyr |
|---------|-------|----------------|-------|
| NA en las claves | coinciden (`na_matches = "na"`) | no coinciden | coinciden; `na_matches="never"` para desactivar |
| Orden de filas | el de `x`; las de `y` sin pareja al final | depende de `maintain_order` | el de `x`; las de `y` sin pareja al final |
| Tipos de claves | tipo común (vctrs) | error o conversión implícita | tipo común; error nombrando `x$col` y `y$col` |
| Columnas repetidas | sufijos `.x` / `.y` | sufijo `_right` | sufijos `.x` / `.y` |
| `by` omitido | columnas en común + mensaje | error | columnas en común + mensaje |
| Varias coincidencias | `multiple = "all"`; advierte muchos-a-muchos | todas | igual que dplyr |
| Desigualdades | `join_by(a >= b)`, `closest()`, rangos | `join_where`, `join_asof` | igual que dplyr |

Los índices de fila en los mensajes de error son base 0.

## La tabla de parejas

Todas las uniones se arman sobre la misma estructura intermedia: una tabla de
dos columnas con **el número de fila de `x` y el de `y`** de cada pareja que
cumple las condiciones (`_match_pairs`). Sobre ella se resuelve todo lo demás,
y por eso `multiple`, `unmatched`, `relationship`, `keep` y `na_matches`
funcionan igual sea cual sea el tipo de condición.

1. Resolver las condiciones (`by=None`, string, lista, diccionario o
   `join_by()`) a una lista de `JoinCondition`, cada una con un operador, una
   columna de `x` y una de `y`.
2. Llevar cada par de columnas comparadas a su tipo común.
3. Calcular las parejas:
   * si hay condiciones de igualdad, un `join` por esas columnas y luego un
     filtro por las desigualdades;
   * si solo hay desigualdades, `join_where` de polars (o un producto
     cartesiano filtrado si la versión de polars no lo trae).
4. Aplicar `closest()`: de las parejas de cada fila de `x`, quedarse con las
   del valor extremo de `y` (el mayor con `>=`/`>`, el menor con `<=`/`<`).
   Los empates se conservan todos.
5. Validar `relationship` y `unmatched`, y avisar de relaciones
   muchos-a-muchos inesperadas. Ese aviso solo aplica a las uniones por
   igualdad: en una por desigualdad la relación muchos-a-muchos es lo normal,
   y dplyr tampoco avisa.
6. Agregar las filas sin pareja que el tipo de unión pida (`left` y `full`
   añaden las de `x`; `right` y `full`, las de `y`) y ordenar por
   (fila de `x`, fila de `y`) con los nulos al final.
7. Aplicar `multiple` y reconstruir las columnas desde `x` e `y`.

## Qué pasa con las columnas de clave

`keep` decide si la clave de `y` sobrevive como columna propia:

| `keep` | Igualdad | Desigualdad |
|--------|----------|-------------|
| `None` (defecto) | una sola columna, con el nombre de `x` | se conservan las dos |
| `True` | las dos, con sufijos si coinciden los nombres | las dos |
| `False` | una sola columna | error |

Cuando la clave se funde en una sola columna, las filas que solo existen en
`y` (en `right_join` y `full_join`) toman ahí el valor de `y`: la columna
resultante es la combinación de las dos, como en dplyr.

Con una desigualdad no hay un valor único que represente a las dos columnas
(`fecha >= inicio` compara cosas distintas), así que fundirlas no significa
nada y `keep=False` es un error explícito en lugar de una elección arbitraria.

## Cómo se escribe un rango

Las tres formas de dplyr se traducen a pares de condiciones:

| Escritura | Condiciones |
|-----------|-------------|
| `between(f.d, f.ini, f.fin)` | `d >= ini`, `d <= fin` |
| `within(f.a, f.b, f.c, f.d)` | `a >= c`, `b <= d` |
| `overlaps(f.a, f.b, f.c, f.d)` | `a <= d`, `b >= c` |

`bounds` (`"[]"`, `"[)"`, `"(]"`, `"()"`) cambia cada comparación a estricta.
En `overlaps()` el extremo cerrado de `y` es el que decide cada una: `"[)"`
hace estricta la comparación contra el extremo superior de `y`, y `"(]"` la
del inferior.

`between()` es la **misma** función que se usa dentro de `mutate()`. Devuelve
un nodo `Between` (subclase de `Call`) que sabe compilarse a una expresión
lógica y que `join_by()` reconoce para traducirlo a dos condiciones. Es la
solución al problema de que en R son dos funciones distintas que se llaman
igual y se distinguen por el contexto, algo que en Python no se puede hacer.

## Uniones filtrantes y `nest_join`

`semi_join` y `anti_join` usan la tabla de parejas y se quedan con los
números de fila de `x` que aparecen (o que no aparecen) en ella. `nest_join`
agrupa la tabla de parejas por fila de `x` y guarda las filas de `y` como una
lista de structs; donde no hay parejas deja una lista vacía, que es el
equivalente de la tabla de 0 filas de dplyr. Los tres aceptan desigualdades
por venir de la misma estructura.

## `bind_rows` y `bind_cols`

* `bind_rows` empareja columnas por nombre, rellena con NA y lleva cada
  columna al tipo común de todas las tablas mediante `cast()` sin pérdida.
* `bind_cols` exige el mismo número de filas (o 1, que se recicla) y repara
  nombres repetidos como vctrs (`a...1`, `a...2`) con un mensaje.

## Operaciones de conjuntos

`union`, `union_all`, `intersect`, `setdiff` y `symdiff` tratan cada fila como
un elemento, así que exigen que las dos tablas tengan **las mismas columnas**;
si no, el error nombra las que sobran y las que faltan. El orden y el nombre
de las columnas del resultado los pone `x`, y cada columna se lleva al tipo
común de las dos.

La pertenencia se resuelve con un `semi`/`anti` join sobre todas las columnas
y `nulls_equal=True`, que es la igualdad de vctrs: NA es igual a NA. Todas
devuelven filas únicas en orden de aparición salvo `union_all()`, que es el
único que conserva repetidas y se diferencia de `bind_rows()` en que no
acepta columnas distintas.

## Pendiente

Nada de la fase 6. Las uniones sobre `LazyFrame` dependen de la tubería
perezosa de la fase 2.
