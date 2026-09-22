"""Genera docs/referencia.md a partir de las docstrings de la API pública.

Uso:  python scripts/gen_reference.py
El test tests/test_docs.py verifica que el archivo esté al día.
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import polyr  # noqa: E402

SECTIONS = [
    ("Expresiones y estructuras", ["f", "NA", "Expr", "GroupedFrame", "DplyrError", "DplyrMessage"]),
    ("Verbos de una tabla", ["filter", "mutate", "select", "rename", "rename_with", "relocate",
                             "arrange", "pull", "distinct", "summarise", "reframe", "count",
                             "tally", "add_count"]),
    ("Filas por posición", ["slice_head", "slice_tail", "slice_min", "slice_max", "slice_sample"]),
    ("Grupos", ["group_by", "ungroup", "group_vars", "n_groups", "group_keys"]),
    ("Dos tablas", ["inner_join", "left_join", "right_join", "full_join", "semi_join",
                    "anti_join", "cross_join", "join_by", "bind_rows", "bind_cols"]),
    ("Conjuntos de filas", ["union", "union_all", "intersect", "setdiff", "symdiff"]),
    ("Resúmenes", ["mean", "sum", "min", "max", "median", "sd", "var", "quantile", "IQR",
                   "mad", "any", "all", "first", "last", "nth", "n_distinct", "n"]),
    ("Condicionales y faltantes", ["is_na", "if_else", "case_when", "case_match", "coalesce",
                                   "na_if", "between", "near"]),
    ("Ventana", ["lag", "lead", "row_number", "min_rank", "dense_rank", "percent_rank",
                 "cume_dist", "ntile", "consecutive_id", "cumsum", "cummean", "cummin",
                 "cummax", "cumall", "cumany", "desc"]),
    ("Varias columnas", ["across", "if_any", "if_all", "pick"]),
    ("Funciones de base R", ["is_in", "abs", "sqrt", "exp", "log", "log2", "log10", "floor",
                             "ceiling", "round", "pmin", "pmax", "as_integer", "as_double",
                             "as_character", "as_logical"]),
    ("Selectores (tidyselect)", ["starts_with", "ends_with", "contains", "matches", "num_range",
                                 "everything", "last_col", "all_of", "any_of", "where"]),
    ("Predicados de tipo (para `where`)", ["is_numeric", "is_integer", "is_double",
                                           "is_character", "is_logical"]),
]

MANUAL = {
    "f": ("f.columna", "Referencia a una columna. También `f[\"nombre\"]` y rangos `f[\"a\":\"c\"]`."),
    "NA": ("NA", "Valor faltante (`mutate(x=NA)`); `None` equivale a `NULL`."),
}


def _signature(name: str, obj) -> str:
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return name
    empty = inspect.Parameter.empty
    sig = sig.replace(parameters=[p.replace(annotation=empty) for p in sig.parameters.values()],
                      return_annotation=inspect.Signature.empty)
    return f"{name}{str(sig).replace(chr(39), chr(34))}"


def _summary(obj) -> str:
    doc = inspect.getdoc(obj) or ""
    paragraph = doc.split("\n\n")[0]
    text = " ".join(line.strip() for line in paragraph.splitlines())
    text = re.sub(r":\w+:`~?(?:[\w.]+\.)?(\w+)`", r"`\1`", text)
    return text.replace("``", "`")


def render() -> str:
    covered = {n for _, names in SECTIONS for n in names}
    missing = sorted(set(polyr.__all__) - covered - {"summarize"})
    if missing:
        raise SystemExit(f"Nombres públicos sin sección en la referencia: {missing}")
    lines = [
        "# Referencia de la API",
        "",
        "<!-- Archivo generado por scripts/gen_reference.py. No editar a mano. -->",
        "",
        f"Versión {polyr.__version__}. Todo se importa desde `polyr`. Los verbos "
        "aceptan llamada directa (`verbo(df, ...)`) o pipe (`df >> verbo(...)`).",
        "",
    ]
    for title, names in SECTIONS:
        lines += [f"## {title}", "", "| Nombre | Descripción |", "|--------|-------------|"]
        for name in names:
            if name in MANUAL:
                sig, desc = MANUAL[name]
            else:
                obj = getattr(polyr, name)
                sig = name if inspect.isclass(obj) else _signature(name, obj)
                desc = _summary(obj)
            desc = desc.replace("|", "\\|")
            lines.append(f"| `{sig}` | {desc} |")
        lines.append("")
    lines += ["`summarize` es un alias de `summarise`.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    (ROOT / "docs" / "referencia.md").write_text(render(), encoding="utf-8")
    print("docs/referencia.md actualizado")
