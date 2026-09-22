---
name: nueva-funcion
description: >
  Agregar una función o un verbo público a polyr sin saltarse ningún paso.
  Cubre dónde va el código, cómo se escribe un nodo de expresión, los cuatro
  sitios donde hay que declararla, las reglas de NA y de tipos que debe
  respetar, y las trampas de polars que ya mordieron antes.
  Usar cuando se agregue, se exporte o se renombre cualquier nombre público
  del paquete, o al cerrar una línea del ROADMAP.
---

# Agregar una función pública a polyr

La regla de oro del paquete: **ante la duda, se hace lo que hace dplyr**. Antes
de escribir nada, mirar qué hace la función en R con NA, con vectores vacíos,
con tipos mezclados y dentro de un grupo. Si se decide desviarse, la desviación
va documentada en `docs/diferencias-con-dplyr.md` con su motivo, y una
desviación sin documentar es un bug.

## 1. Elegir el módulo

| Qué es | Dónde va |
|--------|----------|
| función vectorial de dplyr (resumen, ventana, condicional) | `src/polyr/functions.py` |
| función de base R (`round`, `log`, `as_*`) | `src/polyr/base.py` |
| algo que aplica sobre varias columnas | `src/polyr/across.py` |
| verbo de una tabla | `src/polyr/verbs.py` |
| verbo que resume | `src/polyr/summarise.py` |
| unión o helper de `join_by` | `src/polyr/joins.py` |
| operación de conjuntos | `src/polyr/sets.py` |
| selector | `src/polyr/tidyselect.py` |

## 2. Escribir la función

Una función vectorial devuelve un nodo `Call`. Nada se calcula al construirla:
`compile_` recibe el `EvalContext` y las subexpresiones ya compiladas, y ahí es
donde se consultan los tipos y se aplican las reglas de vctrs.

```python
def mi_funcion(x: Any, na_rm: bool = False) -> Call:
    """Qué hace, en una línea, y en qué se aparta de R si se aparta.

    Los detalles que importan van en viñetas: qué pasa con NA, con un vector
    vacío, con los lógicos.
    """
    def compile_(ctx: EvalContext, e: pl.Expr) -> pl.Expr:
        _numeric_arg(ctx, e, "mi_funcion")       # valida el tipo y falla con vocabulario de R
        ...
        return resultado

    return Call("mi_funcion", compile_, [wrap(x)], "na_rm=True" if na_rm else "")
```

El cuarto argumento de `Call` es el `repr` extra, el que sale en los mensajes de
error (`ℹ En el argumento: ...`). Conviene que muestre solo lo que no es el
valor por defecto.

Un verbo lleva el decorador `@verb` (o `@two_table_verb`), recibe los datos como
argumento **solo posicional** y desenvuelve con `unwrap()` / `rewrap()` para
respetar los grupos.

### Reglas que la función debe respetar

* **NaN es faltante** en los dobles. Usar `_missing()` y `_drop_missing()`, no
  `is_null()` a secas.
* **Con algún NA y sin `na_rm=True`, un resumen es NA**, aunque polars ignore los
  nulos en silencio. Para eso está `_na_guard()`.
* **Tipos:** combinar valores con `ptype_common()`, que nombra los argumentos en
  el error. Convertir con `cast()` de `_types.py`, que falla si hay pérdida.
* **Validar el tipo de entrada** y fallar con el vocabulario de R:
  `` `mi_funcion()` necesita un vector numérico, no <character>. ``
* **Los errores de dentro** son `ExprError`; el verbo los envuelve en
  `DplyrError` con el nombre del verbo y del argumento. No lanzar `DplyrError`
  desde una función vectorial.
* Si el nombre tapa un built-in de Python (`sum`, `any`, `all`, `round`), va con
  `# noqa: A001` y una nota de que es el nombre de R.

## 3. Declararla en los cuatro sitios

Olvidar uno rompe un test o la CI. En orden:

1. El `__all__` del módulo donde se escribió.
2. El import **y** el `__all__` de `src/polyr/__init__.py`.
3. La lista `SECTIONS` de `scripts/gen_reference.py`. Las secciones existentes
   son: Expresiones y estructuras · Verbos de una tabla · Filas por posición ·
   Grupos · Dos tablas · Conjuntos de filas · Resúmenes · Condicionales y
   faltantes · Ventana · Varias columnas · Funciones de base R · Selectores
   (tidyselect) · Predicados de tipo. `gen_reference.py` aborta si un nombre
   público no está en ninguna.
4. Regenerar la referencia: `uv run python scripts/gen_reference.py`. Nunca
   editar `docs/referencia.md` a mano; hay un test que compara el archivo con lo
   que genera el script.

## 4. Tests

Archivo nuevo o el que corresponda en `tests/`, con nombres en español que
describan **la regla**, no la implementación
(`test_mean_con_na_es_na`, no `test_mean_2`). Cubrir siempre:

* el caso normal;
* NA y, si el tipo es doble, NaN;
* `na_rm=True` si existe;
* el vector vacío, si R dice algo particular al respecto;
* el comportamiento dentro de `group_by()`;
* el error de tipo, con `pytest.raises(DplyrError, match=...)`.

Los errores que se lanzan al **construir** la expresión (un `n` no válido, por
ejemplo) son `ExprError` y se prueban sin llamar a ningún verbo.

## 5. Trampas de polars que ya mordieron

* **`sort_by` y `gather` dentro de un `over()` no son deterministas.** Dan
  resultados distintos entre ejecuciones cuando los grupos tienen tamaños
  distintos o la clave de grupo es nula. Si hace falta reordenar dentro de un
  grupo, calcular el lugar de cada fila con `rank("ordinal")` sobre
  `(clave, posición)` y ordenar por ese entero único.
* **`over(order_by=)` anidado dentro de otro `over()` falla en polars 1.30**,
  que es el mínimo declarado.
* **`.first()` sobre un literal falla en 1.30** con `cannot aggregate a
  literal`. Aplicarlo solo si el argumento no es un `Lit`.
* **`Expr.explode()` avisa de deprecación** si no se le pasa `empty_as_null`,
  que no existe en todas las versiones: mirar el patrón `_EXPLODE_HAS_EMPTY`.
* `filterwarnings = ["error::DeprecationWarning"]` está activo, así que
  cualquier aviso de deprecación de polars rompe los tests.

## 6. Cerrar

```bash
uv run pytest -q
uv run ruff check src tests scripts
```

Después, **probar con polars 1.30** (ver `CLAUDE.md`), porque la CI lo hace y
varias de las trampas de arriba solo aparecen ahí.

Por último, actualizar la documentación que corresponda: `ROADMAP.md` si cierra
una línea, `CHANGELOG.md` en la sección `[Sin publicar]`, la lista de funciones
del `README.md`, `docs/diferencias-con-dplyr.md` si hay desviación, y
`docs/tutorial.md` si la función merece un ejemplo (los bloques del tutorial se
ejecutan en los tests, así que el ejemplo queda verificado).

Commit por bloque funcional, con sus tests y la referencia regenerada dentro.
