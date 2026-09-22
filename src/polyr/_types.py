"""Sistema de tipos: el equivalente de vctrs.

Define tres reglas de las que depende la rigurosidad de todo el paquete:

* **Tipo común** (:func:`ptype_common`, como ``vec_ptype2``): a qué tipo se
  llevan varios valores antes de combinarlos. ``logical < integer < double``;
  ``character`` solo se combina con ``character``; un NA sin tipo
  (``unspecified``) se combina con cualquier cosa.
* **Conversión sin pérdida** (:func:`cast`, como ``vec_cast``): convertir a
  un tipo "menor" solo está permitido si no se pierde información
  (``2.0 -> 2`` sí; ``2.5 -> 2`` no).
* **Reciclado** (:func:`recycle`, como ``vec_recycle``): solo se recicla el
  tamaño 1.

Los nombres de los tipos en los mensajes son los de R (``<double>``,
``<character>``...) para que la documentación de dplyr siga siendo válida.
"""
from __future__ import annotations

from typing import Iterable

import polars as pl

from .errors import ExprError

_NUMERIC_RANK = {"logical": 0, "integer": 1, "double": 2}


def kind(dtype: pl.DataType) -> str:
    """Nombre del tipo en el vocabulario de R/vctrs."""
    if dtype == pl.Null:
        return "unspecified"
    if dtype == pl.Boolean:
        return "logical"
    if dtype.is_integer():
        return "integer"
    if dtype.is_float():
        return "double"
    if dtype == pl.String or dtype == pl.Categorical or dtype == pl.Enum:
        return "character"
    if dtype == pl.Date:
        return "date"
    if dtype == pl.Datetime:
        return "datetime"
    if dtype == pl.Duration:
        return "duration"
    if dtype == pl.List:
        return "list"
    if dtype == pl.Struct:
        return "struct"
    return str(dtype)


def type_name(dtype: pl.DataType) -> str:
    """Nombre para mensajes de error, p. ej. ``<double>``."""
    return f"<{kind(dtype)}>"


def is_missing_type(dtype: pl.DataType) -> bool:
    return dtype == pl.Null


# --- tipo común ---------------------------------------------------------------

def _common2(la: str, a: pl.DataType, lb: str, b: pl.DataType) -> pl.DataType:
    if a == b:
        return a
    ka, kb = kind(a), kind(b)
    if ka in _NUMERIC_RANK and kb in _NUMERIC_RANK:
        top = max(ka, kb, key=_NUMERIC_RANK.__getitem__)
        if top == "logical":
            return pl.Boolean
        if top == "integer":
            ints = [d for d in (a, b) if kind(d) == "integer"]
            if len(ints) == 1:
                return ints[0]
            if a.is_signed_integer() and b.is_signed_integer():
                return a if _int_bits(a) >= _int_bits(b) else b
            return pl.Int64
        return pl.Float64
    if ka == kb == "character":
        return pl.String
    raise ExprError(
        f"No se puede combinar `{la}` {type_name(a)} con `{lb}` {type_name(b)}."
    )


def _int_bits(dtype: pl.DataType) -> int:
    for candidate, bits in ((pl.Int8, 8), (pl.Int16, 16), (pl.Int32, 32), (pl.Int64, 64),
                            (pl.UInt8, 8), (pl.UInt16, 16), (pl.UInt32, 32), (pl.UInt64, 64)):
        if dtype == candidate:
            return bits
    return 64


def ptype_common(items: Iterable[tuple[str, pl.DataType]]) -> pl.DataType:
    """Tipo común de varios valores etiquetados ``(nombre, dtype)``.

    Lanza :class:`ExprError` si dos tipos son incompatibles, nombrando los
    argumentos involucrados.
    """
    result: pl.DataType = pl.Null
    result_label = ""
    for label, dtype in items:
        if is_missing_type(dtype):
            continue
        if is_missing_type(result):
            result, result_label = dtype, label
            continue
        result = _common2(result_label, result, label, dtype)
    return result


# --- conversión sin pérdida ---------------------------------------------------

def cast(s: pl.Series, to: pl.DataType, arg: str = "x") -> pl.Series:
    """Convierte ``s`` a ``to`` sin pérdida de información (``vec_cast``).

    * Hacia un tipo mayor (``integer -> double``) siempre funciona.
    * Hacia un tipo menor (``double -> integer``, ``integer -> logical``)
      solo si todos los valores sobreviven la conversión de ida y vuelta.
    * Entre familias distintas (``double -> character``) nunca.
    """
    if s.dtype == to:
        return s
    k_from, k_to = kind(s.dtype), kind(to)
    if k_from == "unspecified":
        return s.cast(to)
    compatible = (
        (k_from in _NUMERIC_RANK and k_to in _NUMERIC_RANK)
        or (k_from == k_to)
    )
    if not compatible:
        raise ExprError(
            f"No se puede convertir `{arg}` {type_name(s.dtype)} a {type_name(to)}."
        )
    out = s.cast(to, strict=False)
    back = out.cast(s.dtype, strict=False)
    lossy = (s.is_not_null() & (back != s).fill_null(True))
    if s.dtype.is_float():
        lossy = lossy | (s.is_nan().fill_null(False) & (k_to != "double"))
    if lossy.any():
        where = lossy.arg_true().to_list()
        shown = ", ".join(map(str, where[:5])) + (", ..." if len(where) > 5 else "")
        raise ExprError(
            f"No se puede convertir `{arg}` {type_name(s.dtype)} a {type_name(to)} "
            f"sin perder precisión.\n• Índices (base 0): {shown}"
        )
    return out


# --- tamaño y reciclado -------------------------------------------------------

def recycle(s: pl.Series, n: int, what: str) -> pl.Series:
    """Reglas de reciclado de vctrs: solo se recicla el tamaño 1."""
    if len(s) == n:
        return s
    if len(s) == 1:
        return s.new_from_index(0, n)
    raise ExprError(f"{what} debe tener tamaño {n} o 1, no {len(s)}.")


# --- predicados para where() --------------------------------------------------

def is_numeric(s: pl.Series) -> bool:
    """Como ``is.numeric()``: enteros y dobles (los lógicos no cuentan)."""
    return kind(s.dtype) in ("integer", "double")


def is_integer(s: pl.Series) -> bool:
    """Como ``is.integer()``: columnas de enteros."""
    return kind(s.dtype) == "integer"


def is_double(s: pl.Series) -> bool:
    """Como ``is.double()``: columnas de dobles."""
    return kind(s.dtype) == "double"


def is_character(s: pl.Series) -> bool:
    """Como ``is.character()``: columnas de texto."""
    return kind(s.dtype) == "character"


def is_logical(s: pl.Series) -> bool:
    """Como ``is.logical()``: columnas lógicas."""
    return kind(s.dtype) == "logical"
