# Cómo contribuir

¡Gracias por tu interés! polyr tiene una regla que está por encima de todas
las demás.

## Regla de oro

**dplyr es la especificación.** Antes de implementar algo, se verifica qué
hace dplyr (≥ 1.1) en R y se reproduce, incluidos los casos borde. Si una
diferencia es inevitable o deliberada, se documenta en
`docs/diferencias-con-dplyr.md`. Una diferencia no documentada es un bug.

## Preparar el entorno

```bash
git clone https://github.com/rneiraa/polyr.git && cd polyr
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check src tests scripts
```

## Arquitectura

| Módulo | Equivale a | Responsabilidad |
|--------|------------|-----------------|
| `_types.py` | vctrs | Tipos, tipo común, conversión, reciclado |
| `expr.py` | rlang | Árbol de expresiones y compilación |
| `tidyselect.py` | tidyselect | Lenguaje de selección de columnas |
| `grouped.py` | `grouped_df` | Data frame agrupado |
| `_core.py` | — | Pipe, data mask, evaluación por grupos, errores |
| `verbs.py` | dplyr | Verbos fila a fila y de agrupación |
| `summarise.py` | dplyr | `summarise`, `reframe`, `count`... |
| `slice.py` | dplyr | Familia `slice_*` |
| `joins.py`, `bind.py` | dplyr | Dos tablas |
| `functions.py` | dplyr | Funciones vectoriales |
| `across.py` | dplyr | `across`, `if_any`, `if_all` |
| `base.py` | base R | Funciones de base R de uso diario |
| `errors.py` | cli/rlang | Errores y mensajes |

Las capas internas lanzan `ExprError`; solo los verbos lanzan `DplyrError`,
agregando el verbo y el argumento.

## Agregar una función vectorial

1. Escribe una función que devuelva `Call(nombre, compile_, args)`.
2. `compile_(ctx, *exprs)` recibe las expresiones de polars ya compiladas y
   un `EvalContext`; usa `ctx.dtype(expr)` para aplicar las reglas de tipos.
3. Documenta en la docstring **en qué difiere de polars**.
4. Exporta en `__init__.py`, agrégala a una sección de
   `scripts/gen_reference.py` y ejecuta `python scripts/gen_reference.py`.

## Tests

* Un archivo por verbo o capa en `tests/`.
* Cada caso borde reproducido lleva su test; si difiere de polars, un
  comentario lo explica.
* Los tests portados desde dplyr indican el origen:
  `# dplyr: tests/testthat/test-filter.R`.
* Los mensajes de error se prueban con `pytest.raises(..., match=...)`.
* Los ejemplos de `README.md` y `docs/tutorial.md` se ejecutan en los tests.

## Estilo

* `ruff check` sin errores.
* Docstrings y mensajes en español; nombres de la API idénticos a dplyr.
* Argumentos con punto en dplyr (`.keep`) llevan guion bajo (`_keep`).
* Un argumento que existe pero aún no funciona lanza un error explícito;
  nunca se ignora en silencio.

## Pull requests

* Una funcionalidad por PR, con tests y entrada en `CHANGELOG.md`.
* Si cambia el comportamiento, explica qué hace dplyr en ese caso (idealmente
  con el código R y su salida).
