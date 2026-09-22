# polyr

La gramática de dplyr en Python, con la **misma semántica**, sobre polars.

**Principio rector: ante la duda, se hace lo que hace dplyr.** Toda desviación
se documenta en `docs/diferencias-con-dplyr.md` con su motivo. Cualquier
diferencia no listada ahí es un bug.

Los mensajes de error, los nombres de los tipos (`<double>`, `<character>`) y
la documentación están en español y siguen el formato de dplyr/rlang.

## Entorno

No hay `pip` en esta máquina, solo `uv`. El intérprete vive en `.venv/`.

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"  # una vez
uv run pytest -q
uv run ruff check src tests scripts
uv run python scripts/gen_reference.py
```

`uv run` encuentra `.venv` solo; no hace falta escribir `.venv/bin/python`.

## Antes de subir: probar con polars 1.30

`pyproject.toml` declara `polars>=1.30` y la CI tiene un job fijado a esa
versión. Lo que funciona en la última no siempre funciona ahí: `over(order_by=)`
anidado y `.first()` sobre un literal fallan en 1.30. Verificar con un venv
aparte antes de empujar a `main`.

```bash
uv venv /tmp/v130 && uv pip install --python /tmp/v130/bin/python -e ".[dev]" \
  && uv pip install --python /tmp/v130/bin/python "polars==1.30.0"
/tmp/v130/bin/python -m pytest -q
```

## Agregar una función pública

Hay un skill con el procedimiento completo: `.claude/skills/nueva-funcion/`.
En resumen, una función nueva se declara en **cuatro** sitios, y olvidar uno
rompe un test o la CI:

1. El módulo que le corresponde (ver mapa más abajo) y su `__all__`.
2. El import y el `__all__` de `src/polyr/__init__.py`.
3. La sección que le toque en `SECTIONS`, dentro de `scripts/gen_reference.py`.
4. `docs/referencia.md`, regenerado (nunca a mano).

## Mapa de módulos

| Módulo | Qué contiene |
|--------|--------------|
| `expr.py` | árbol de expresiones perezosas; el equivalente de rlang |
| `_types.py` | tipo común, conversión sin pérdida, reciclado; el equivalente de vctrs |
| `tidyselect.py` | lenguaje de selección de columnas |
| `_core.py` | pipe `>>`, data mask, manejo de errores, infraestructura de los verbos |
| `verbs.py` | verbos de una fila por fila: `filter`, `mutate`, `select`, `arrange`... |
| `summarise.py` | `summarise`, `reframe`, `count`, `tally`, `add_count` |
| `slice.py` | `slice_head`, `slice_tail`, `slice_min`, `slice_max`, `slice_sample` |
| `grouped.py` | `GroupedFrame` |
| `functions.py` | funciones vectoriales de dplyr (resúmenes, ventana, condicionales) |
| `base.py` | funciones de base R (`is_in`, `round`, `log`, `pmin`, `as_*`) |
| `across.py` | `across`, `if_any`, `if_all`, `pick` |
| `joins.py` | las siete uniones, `join_by`, `closest`, `within`, `overlaps`, `nest_join` |
| `sets.py` | `union`, `union_all`, `intersect`, `setdiff`, `symdiff` |
| `bind.py` | `bind_rows`, `bind_cols` |

Los documentos de diseño (`docs/diseno/01` a `05`) explican el porqué de cada
capa. Si un cambio altera la maquinaria que describen, se actualizan con él.

## Convenciones

* Los argumentos que en dplyr empiezan con punto (`.keep`, `.by`) aquí empiezan
  con guion bajo (`_keep`, `_by`).
* El data frame es un argumento solo posicional, para que una columna pueda
  llamarse `data`.
* Las posiciones de fila son base 0, **salvo `nth()`**, que cuenta desde 1 como
  en R. Es la única excepción y está justificada en `diferencias-con-dplyr.md`.
* Los rankings (`row_number`, `ntile`...) empiezan en 1: son valores, no índices.
* Un argumento que existe pero todavía no funciona lanza un error explícito;
  nunca se ignora en silencio.
* Los mensajes informativos de dplyr se emiten como `DplyrMessage`.
* NaN cuenta como faltante en los dobles, como en vctrs.

## Tests

Los ejemplos de `README.md` y `docs/tutorial.md` se ejecutan en
`tests/test_docs.py`, así que un cambio de API los rompe. Los tests se llaman
en español y describen la regla que verifican, no la implementación.

Cuidado con lo que no es determinista: `sort_by` y `gather` dentro de un
`over()` dan resultados que cambian entre ejecuciones. Si un resultado depende
del orden, verificarlo repitiendo la operación y comparando contra una
referencia calculada en Python.

## Git

Los commits se firman como `polyr <polyr@users.noreply.github.com>`, que ya es
el `user.email` local del repo: **no pasar `-c user.name` ni `-c user.email`**
al commitear, y nunca usar un correo personal en un repo público.

Rama de trabajo por fase del ROADMAP y un commit por bloque funcional (cada
grupo de funciones con sus tests y la referencia regenerada), no un commit
grande al final. Cada commit deja `pytest` y `ruff` en verde.

Remoto: <https://github.com/rneiraa/polyr>.

## Plan de trabajo

`ROADMAP.md`. Fases 0, 3, 5 y 6 cerradas. Abiertas: 1 (fechas, factores,
columnas lista), 2 (pronombres `.data`/`.env`, `LazyFrame`), 3 (`slice()`
posicional, renombrado múltiple, `reframe` secuencial), 4 (`rowwise`,
`cur_group*`, `group_split/map/modify/nest`) y 7 (madurez: testing diferencial
contra R con rpy2 + hypothesis, PyPI).
