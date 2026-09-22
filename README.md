# polyr

**La gramática de dplyr en Python, con la misma semántica.**

[![CI](https://github.com/OWNER/polyr/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/polyr/actions/workflows/ci.yml)
![Estado: beta](https://img.shields.io/badge/estado-beta-orange)
![Python ≥ 3.10](https://img.shields.io/badge/python-%E2%89%A53.10-blue)

polyr no es "una API parecida a dplyr": su objetivo es que el mismo análisis
dé **el mismo resultado que en R**, incluidos los casos borde que suelen
romper las traducciones (NA, NaN, tipos, reciclado, orden de filas y de
grupos, uniones con NA). Usa [polars](https://pola.rs) como motor y agrega
encima las tres capas que hacen riguroso a dplyr:

| Capa | En R | En polyr |
|------|------|----------|
| Tipos: tipo común, conversión sin pérdida, reciclado | vctrs | `polyr._types` |
| Evaluación de expresiones sobre columnas | rlang | `polyr.expr` |
| Lenguaje de selección de columnas | tidyselect | `polyr.tidyselect` |

## Instalación

```bash
pip install git+https://github.com/OWNER/polyr.git
```

Requiere Python ≥ 3.10 y polars ≥ 1.30.

## Un vistazo

```python
import polars as pl
from polyr import (f, filter, mutate, group_by, summarise, arrange, desc, left_join,
                   n, mean, if_else, is_na)

vuelos = pl.DataFrame({
    "aerolinea": ["LA", "LA", "H2", "JA", "LA", "H2", "JA"],
    "origen":    ["SCL", "SCL", "LIM", "SCL", "EZE", "LIM", "SCL"],
    "retraso":   [12.0, None, -3.0, 45.0, 8.0, float("nan"), 0.0],
})
aerolineas = pl.DataFrame({"aerolinea": ["LA", "H2", "JA"],
                           "nombre": ["LATAM", "Sky", "JetSMART"]})

resumen = (
    vuelos
    >> filter(~is_na(f.retraso))
    >> mutate(tarde=if_else(f.retraso > 10, "sí", "no"))
    >> group_by(f.aerolinea)
    >> summarise(vuelos=n(), retraso_medio=mean(f.retraso))
    >> left_join(aerolineas, by="aerolinea")
    >> arrange(desc(f.retraso_medio))
)
```

## Equivalencias rápidas

| dplyr (R) | polyr |
|-----------|-------|
| `df %>% filter(x > 1, y == "a")` | `df >> filter(f.x > 1, f.y == "a")` |
| `x > 1 & y < 2` | `(f.x > 1) & (f.y < 2)` |
| `x %in% c("a", "b")` | `is_in(f.x, ["a", "b"])` |
| `mutate(z = x * 2, .keep = "used")` | `mutate(z=f.x * 2, _keep="used")` |
| `mutate(x = NULL)` / `x = NA` | `mutate(x=None)` / `x=NA` |
| `summarise(m = mean(x), .by = g)` | `summarise(m=mean(f.x), _by=f.g)` |
| `select(a:c, -b, nuevo = d)` | `select(f["a":"c"], -f.b, nuevo=f.d)` |
| `across(where(is.numeric), mean)` | `across(where(is_numeric), mean)` |
| `case_when(x < 0 ~ "neg", .default = "pos")` | `case_when((f.x < 0, "neg"), _default="pos")` |
| `case_match(x, c("a", "b") ~ "ab")` | `case_match(f.x, (["a", "b"], "ab"))` |
| `dense_rank(pick(a, b))` | `dense_rank(pick(f.a, f.b))` |
| `left_join(x, y, join_by(id == codigo))` | `left_join(x, y, by=join_by(f.id == f.codigo))` |
| `join_by(between(d, ini, fin))` | `join_by(between(f.d, f.ini, f.fin))` |
| `join_by(closest(d >= corte))` | `join_by(closest(f.d >= f.corte))` |

La lista completa de diferencias, con su justificación, está en
[docs/diferencias-con-dplyr.md](docs/diferencias-con-dplyr.md).

> **Nota sobre los imports.** polyr exporta funciones con los mismos nombres
> que en R, y algunos coinciden con built-ins de Python (`filter`, `sum`,
> `min`, `max`, `abs`, `round`). Importa explícitamente lo que uses; evita
> `from polyr import *`.

## Qué incluye esta beta

* **Verbos:** `filter`, `mutate`, `select`, `rename`, `rename_with`,
  `relocate`, `arrange`, `pull`, `distinct`, `summarise`, `reframe`,
  `count`, `tally`, `add_count`, `slice_head`, `slice_tail`, `slice_min`,
  `slice_max`, `slice_sample`.
* **Grupos:** `group_by`, `ungroup`, `_by` por operación, `group_vars`,
  `n_groups`, `group_keys`.
* **Dos tablas:** `inner_join`, `left_join`, `right_join`, `full_join`,
  `semi_join`, `anti_join`, `cross_join`, `nest_join`, `bind_rows`,
  `bind_cols`, y `join_by` con igualdades, desigualdades, rangos
  (`between`, `within`, `overlaps`) y `closest`.
* **Conjuntos de filas:** `union`, `union_all`, `intersect`, `setdiff`,
  `symdiff`.
* **Funciones:** resúmenes (`mean`, `sum`, `min`, `max`, `median`, `sd`,
  `var`, `quantile`, `IQR`, `mad`, `any`, `all`, `first`, `last`, `nth`,
  `n_distinct`, `n`), condicionales (`if_else`, `case_when`, `case_match`,
  `coalesce`, `na_if`, `between`, `near`), ventana (`lag` y `lead`, las dos
  con `order_by=`, rankings, `ntile`, `consecutive_id`, acumulados), `across`,
  `if_any`, `if_all`, `pick` y funciones de base R (`is_in`, `round`, `log`,
  `pmin`, `as_integer`, ...).
* **tidyselect** completo para una tabla.

Lo que falta está en el [ROADMAP](ROADMAP.md).

## Documentación

* [Tutorial](docs/tutorial.md)
* [Referencia de la API](docs/referencia.md)
* [Diferencias con dplyr](docs/diferencias-con-dplyr.md)
* Diseño: [expresiones](docs/diseno/01-expresiones.md) ·
  [tipos](docs/diseno/02-tipos.md) · [tidyselect](docs/diseno/03-tidyselect.md) ·
  [grupos](docs/diseno/04-grupos.md) · [uniones](docs/diseno/05-uniones.md)
* [Cómo contribuir](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## Desarrollo

```bash
git clone https://github.com/OWNER/polyr.git && cd polyr
pip install -e ".[dev]"
pytest
ruff check src tests
```

## Licencia

MIT. polyr reproduce el comportamiento de dplyr, vctrs y tidyselect
(Posit PBC, MIT); ver [LICENSE](LICENSE).
