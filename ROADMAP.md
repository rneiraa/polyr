# Roadmap

Principio rector: **ante la duda, se hace lo que hace dplyr**. Cada desviación
se documenta en [docs/diferencias-con-dplyr.md](docs/diferencias-con-dplyr.md)
con su motivo.

Estado: ✅ completo · 🔨 parcial · ⏳ pendiente

## ✅ Fase 0 — Cimientos
- [x] Paquete (`src/`, `pyproject.toml`, pytest, ruff, CI en Python 3.10–3.13)
- [x] Motor de cómputo: polars ≥ 1.30
- [x] Sintaxis `f.columna`; pipe `>>` equivalente a la llamada directa
- [x] La documentación se ejecuta en los tests; la referencia se genera sola

## 🔨 Fase 1 — Sistema de tipos (vctrs) · `_types.py`
- [x] Vocabulario de tipos de R en los mensajes
- [x] Tipo común (`vec_ptype2`), conversión sin pérdida (`vec_cast`), reciclado
- [x] NaN como faltante en dobles
- [ ] Fechas y datetimes: tipo común `date`/`datetime`, zonas horarias
- [ ] Factores (`Categorical`/`Enum`) con niveles y `.drop = FALSE`
- [ ] Columnas lista y data frames anidados

## 🔨 Fase 2 — Expresiones (rlang) · `expr.py`
- [x] Árbol perezoso con compilación consciente de tipos
- [x] Errores con el formato de dplyr
- [x] Protección contra `and`/`or`/`not` y comparaciones encadenadas
- [ ] Pronombres `.data` / `.env` para programar funciones propias
- [ ] Evaluación perezosa de toda la tubería con `LazyFrame`

## ✅ Fase 3 — Verbos de una tabla y tidyselect
- [x] tidyselect: nombres, rangos, `-`, `~`, `|`, `&`, todos los helpers
- [x] `filter`, `mutate` (`_keep`, `_before`, `_after`, `_by`), `select`, `rename`,
      `rename_with`, `relocate`, `arrange`, `pull`, `distinct`
- [x] `summarise` (secuencial, `_groups`, `_by`), `reframe`
- [x] `count`, `tally`, `add_count`
- [x] `slice_head`, `slice_tail`, `slice_min`, `slice_max`, `slice_sample`
- [ ] `slice()` con posiciones (pendiente de decisión base 0/base 1)
- [ ] `slice_sample(replace=, weight_by=)`
- [ ] Renombrado múltiple con sufijos (`select(x = starts_with("a"))`)
- [ ] `reframe` secuencial

## 🔨 Fase 4 — Agrupación
- [x] `group_by` (con expresiones y `_add`), `ungroup`, `group_vars`, `n_groups`, `group_keys`
- [x] Semántica de grupos en todos los verbos; `_by`
- [x] Mensajes de `summarise` como `DplyrMessage`
- [ ] `rowwise()`
- [ ] `cur_group()`, `cur_group_id()`, `cur_group_rows()`
- [ ] `group_split()`, `group_map()`, `group_modify()`, `group_nest()`

## 🔨 Fase 5 — Funciones vectoriales
- [x] Resúmenes: `mean`, `sum`, `min`, `max`, `median`, `sd`, `var`, `first`, `last`, `n_distinct`, `n`
- [x] `if_else`, `case_when`, `coalesce`, `na_if`, `between`, `near`
- [x] `lag`, `lead`, `row_number`, `min_rank`, `dense_rank`, `percent_rank`, `cume_dist`, `ntile`
- [x] `cumsum`, `cummean`, `cummin`, `cummax`, `cumall`, `cumany`
- [x] `across`, `if_any`, `if_all`
- [x] Base R: `is_in`, `abs`, `sqrt`, `exp`, `log*`, `floor`, `ceiling`, `round`, `pmin`, `pmax`, `as_*`
- [x] `case_match`, `consecutive_id`, `nth` (base 1, como en R), `pick`
- [x] `lag(order_by=)`, `lead(order_by=)`, `quantile`, `IQR`, `mad`, `any`/`all`
- [ ] stringr y lubridate básicos (probablemente en paquetes aparte)

## ✅ Fase 6 — Combinación de tablas
- [x] `inner_join`, `left_join`, `right_join`, `full_join`, `semi_join`, `anti_join`, `cross_join`
- [x] `join_by` por igualdad; `multiple`, `unmatched`, `relationship`, `na_matches`, `suffix`
- [x] `bind_rows` (tipo común, `_id`), `bind_cols` (reparación de nombres)
- [x] `join_by` con desigualdades, `closest()`, `between()`, `within()`, `overlaps()`
- [x] `keep=True`, `nest_join`
- [x] `union`, `union_all`, `intersect`, `setdiff`, `symdiff`

## ⏳ Fase 7 — Madurez (camino a 1.0)
- [ ] Testing diferencial contra R (rpy2 + hypothesis)
- [ ] Portar sistemáticamente la suite de tests de dplyr
- [ ] Rendimiento: tubería perezosa, benchmarks contra polars puro
- [ ] Sitio de documentación y publicación en PyPI
- [ ] Documentación en inglés
