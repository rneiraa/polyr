# Diseño: sistema de tipos

**Módulo:** `polyr/_types.py` · **Equivale a:** vctrs

La rigurosidad de dplyr 1.x no viene de C: viene de vctrs, que define reglas
explícitas para combinar, convertir y reciclar vectores. polyr las reproduce
sobre los tipos de polars.

## Vocabulario

| polars                          | R / vctrs       |
|---------------------------------|-----------------|
| `Boolean`                       | `<logical>`     |
| `Int8…Int64`, `UInt8…UInt64`    | `<integer>`     |
| `Float32`, `Float64`            | `<double>`      |
| `String`, `Categorical`, `Enum` | `<character>`   |
| `Null`                          | `<unspecified>` |
| `Date` / `Datetime` / `Duration`| `<date>` / `<datetime>` / `<duration>` |

Los mensajes de error usan los nombres de R.

## Tipo común (`ptype_common`, como `vec_ptype2`)

```
unspecified  +  T         →  T
logical      +  integer   →  integer
integer      +  double    →  double
character    +  character →  character
double       +  character →  ERROR: No se puede combinar `a` <double> con `b` <character>.
```

Entre enteros de distinta anchura se elige el más ancho con signo; si se
mezclan con y sin signo, `Int64`.

Lo usan `if_else` y `coalesce`, y lo usarán `case_when`, `bind_rows` y los
joins.

## Conversión sin pérdida (`cast`, como `vec_cast`)

* Hacia arriba (`integer → double`) siempre funciona.
* Hacia abajo solo si cada valor sobrevive la ida y vuelta:
  `[1.0, 2.0] → [1, 2]` funciona; `[1.0, 2.5]` falla indicando los índices.
* NaN e infinito no pueden convertirse a entero.
* Entre familias (`double → character`) nunca, igual que en vctrs.

## Reciclado (`recycle`)

Solo se recicla el tamaño 1. Cualquier otro tamaño distinto de `n` es error:
`` `z` debe tener tamaño 3 o 1, no 2. ``

## Valores faltantes

Como `vec_detect_missing`: en dobles, **NaN también es faltante**. Esto
afecta a `is_na`, `mean(na_rm=True)`, `coalesce` y `arrange` (NaN va al
final junto con NA).

## Diferencias semánticas con polars que esta capa corrige

| Caso                                   | polars              | polyr (= R)          |
|----------------------------------------|---------------------|--------------------|
| `mean` con nulos                       | los ignora          | NA                 |
| `is_null(NaN)`                         | False               | `is_na(NaN)` True  |
| `when(NA).then(a).otherwise(b)`        | b                   | `if_else` → NA     |
| `int ** int`                           | entero              | double             |
| orden descendente con NaN              | NaN primero         | al final           |

## Pendiente
Fechas y datetimes (tipo común, zonas horarias), factores con niveles,
columnas lista.
