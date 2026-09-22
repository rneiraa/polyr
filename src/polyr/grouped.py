"""Data frame agrupado: el equivalente de ``grouped_df`` en dplyr.

Un :class:`GroupedFrame` es un ``polars.DataFrame`` más la lista de columnas
de agrupación. No copia datos: los verbos leen ``.data`` y ``.groups`` y
devuelven un nuevo ``GroupedFrame`` cuando corresponde.
"""
from __future__ import annotations

from typing import Any, Sequence

import polars as pl

__all__ = ["GroupedFrame"]


class GroupedFrame:
    """Data frame con grupos. Se crea con :func:`polyr.group_by`."""

    __slots__ = ("_data", "_groups")

    def __init__(self, data: pl.DataFrame, groups: Sequence[str]):
        groups = list(dict.fromkeys(groups))
        missing = [g for g in groups if g not in data.columns]
        if missing:
            raise ValueError(f"Las columnas de agrupación no existen: {missing}")
        self._data = data
        self._groups = groups

    # --- acceso -----------------------------------------------------------
    @property
    def data(self) -> pl.DataFrame:
        """Los datos, sin información de grupos."""
        return self._data

    @property
    def groups(self) -> list[str]:
        """Nombres de las columnas de agrupación."""
        return list(self._groups)

    @property
    def columns(self) -> list[str]:
        return self._data.columns

    @property
    def schema(self) -> pl.Schema:
        return self._data.schema

    @property
    def shape(self) -> tuple[int, int]:
        return self._data.shape

    @property
    def height(self) -> int:
        return self._data.height

    @property
    def width(self) -> int:
        return self._data.width

    def __len__(self) -> int:
        return self._data.height

    def __getitem__(self, key: Any) -> Any:
        return self._data[key]

    def group_keys(self) -> pl.DataFrame:
        """Una fila por grupo, ordenadas como en dplyr (NA al final)."""
        return (self._data.select(self._groups).unique()
                .sort(self._groups, nulls_last=True, maintain_order=True))

    @property
    def n_groups(self) -> int:
        return self._data.select(self._groups).unique().height

    def ungroup(self) -> pl.DataFrame:
        return self._data

    def to_polars(self) -> pl.DataFrame:
        return self._data

    # --- impresión --------------------------------------------------------
    def _header(self) -> str:
        return f"# Grupos: {', '.join(self._groups)} [{self.n_groups}]"

    def __repr__(self) -> str:
        return f"{self._header()}\n{self._data!r}"

    def _repr_html_(self) -> str:
        return f"<p><code>{self._header()}</code></p>{self._data._repr_html_()}"
