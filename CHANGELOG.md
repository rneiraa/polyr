# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
versionado [semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Nuevo
* **Resúmenes:** `quantile` (interpolación lineal, el `type = 7` de R), `IQR`,
  `mad`, `any` y `all` con la lógica de tres valores de R, y `nth`.
* **Recodificación:** `case_match`, la versión de `case_when` para comparar
  una columna con listas de valores.
* **Ventana:** `consecutive_id`, y `order_by=` en `lag` y `lead`.
* **Varias columnas:** `pick`, que entrega columnas juntas a una función que
  las necesita a la vez (`dense_rank(pick(a, b))`).

* **Uniones:** `join_by()` acepta desigualdades (`f.a >= f.b`), rangos
  (`between`, `within`, `overlaps`) y `closest()`; `keep=True` conserva las
  claves de las dos tablas y `nest_join()` guarda las parejas en una celda.
* **Conjuntos de filas:** `union`, `union_all`, `intersect`, `setdiff` y
  `symdiff`.
* `between()` gana el argumento `bounds` (`"[]"`, `"[)"`, `"(]"`, `"()"`).

### Corregido
* Los rankings sobre varias columnas devuelven NA en las filas con algún
  faltante, como `vec_rank(incomplete = "na")` en dplyr.

### Decisiones
* `nth(x, n)` cuenta desde 1 y admite negativos desde el final, igual que en
  R. Es la excepción a la regla de base 0 de polyr, y está justificada en
  [docs/diferencias-con-dplyr.md](docs/diferencias-con-dplyr.md).

## [0.2.0b1] — primera beta pública

### Nuevo
* **Grupos:** `group_by` (con expresiones y `_add`), `ungroup`, `GroupedFrame`,
  `group_vars`, `n_groups`, `group_keys`, y `_by` en `filter`, `mutate`,
  `summarise`, `reframe` y `slice_*`.
* **Verbos:** `summarise`/`summarize` (secuencial, `_groups`), `reframe`,
  `count`, `tally`, `add_count`, `distinct`, `rename_with`, `slice_head`,
  `slice_tail`, `slice_min`, `slice_max`, `slice_sample`.
* **Uniones:** `inner_join`, `left_join`, `right_join`, `full_join`,
  `semi_join`, `anti_join`, `cross_join`, `join_by`, `bind_rows`, `bind_cols`.
* **Funciones:** `sum`, `min`, `max`, `median`, `sd`, `var`, `first`,
  `last`, `n_distinct`, `case_when`, `na_if`, `between`, `near`, `lag`,
  `lead`, `row_number`, `min_rank`, `dense_rank`, `percent_rank`,
  `cume_dist`, `ntile`, `cumsum`, `cummean`, `cummin`, `cummax`, `cumall`,
  `cumany`, `across`, `if_any`, `if_all`.
* **Base R:** `is_in`, `abs`, `sqrt`, `exp`, `log`, `log2`, `log10`,
  `floor`, `ceiling`, `round`, `pmin`, `pmax`, `as_integer`, `as_double`,
  `as_character`, `as_logical`.
* `DplyrMessage` para los mensajes informativos.
* Tutorial ejecutable, referencia generada automáticamente, documentos de
  diseño de grupos y uniones.

### Cambios
* El paquete pasa a llamarse **polyr** (`dpy` estaba ocupado en PyPI).
* Requiere polars ≥ 1.30.

## [0.1.0]
* Sistema de tipos (vctrs), expresiones con contexto de tipos, tidyselect.
* `select`, `rename`, `relocate`, `arrange`, `pull`; `mutate` con `_keep`,
  `_before`, `_after`; `if_else`, `coalesce`, `n`, `desc`.

## [0.0.1]
* Prototipo: expresiones `f.x`, `filter`, `mutate`, `mean`, `is_na`.
