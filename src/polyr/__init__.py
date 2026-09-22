"""polyr: la gramática de dplyr en Python, con la misma semántica.

>>> import polars as pl
>>> from polyr import f, filter, mutate
>>> df = pl.DataFrame({"x": [1, 2, 3]})
>>> (df >> filter(f.x > 1) >> mutate(y=f.x * 2))["y"].to_list()
[4, 6]
"""
from ._types import is_character, is_double, is_integer, is_logical, is_numeric
from .across import across, if_all, if_any, pick
from .bind import bind_cols, bind_rows
from .errors import DplyrError, DplyrMessage
from .expr import NA, Expr, f
from .functions import (IQR, all, any, between, case_match, case_when, coalesce,
                        consecutive_id, cumall, cumany, cummax, cummean, cummin, cume_dist,
                        cumsum, dense_rank, desc, first, if_else, is_na, lag, last, lead,
                        mad, max, mean, median, min, min_rank, n, n_distinct, na_if, near,
                        nth, ntile, percent_rank, quantile, row_number, sd, sum, var)
from .grouped import GroupedFrame
from .base import (abs, as_character, as_double, as_integer, as_logical, ceiling, exp,
                   floor, is_in, log, log2, log10, pmax, pmin, round, sqrt)
from .joins import (anti_join, cross_join, full_join, inner_join, join_by, left_join,
                    nest_join, right_join, semi_join)
from .sets import intersect, setdiff, symdiff, union, union_all
from .slice import slice_head, slice_max, slice_min, slice_sample, slice_tail
from .summarise import add_count, count, reframe, summarise, summarize, tally
from .tidyselect import (all_of, any_of, contains, ends_with, everything, last_col,
                         matches, num_range, starts_with, where)
from .verbs import (arrange, distinct, filter, group_by, group_keys, group_vars, mutate,
                    n_groups, pull, relocate, rename, rename_with, select, ungroup)

__version__ = "0.2.0b1"

__all__ = [
    # expresiones y tipos de datos
    "f", "NA", "Expr", "GroupedFrame", "DplyrError", "DplyrMessage",
    # verbos de una tabla
    "filter", "mutate", "select", "rename", "rename_with", "relocate", "arrange", "pull",
    "distinct", "summarise", "summarize", "reframe", "count", "tally", "add_count",
    "slice_head", "slice_tail", "slice_min", "slice_max", "slice_sample",
    # grupos
    "group_by", "ungroup", "group_vars", "n_groups", "group_keys",
    # dos tablas
    "inner_join", "left_join", "right_join", "full_join", "semi_join", "anti_join",
    "cross_join", "nest_join", "join_by", "bind_rows", "bind_cols",
    "union", "union_all", "intersect", "setdiff", "symdiff",
    # funciones vectoriales
    "mean", "sum", "min", "max", "median", "sd", "var", "first", "last", "n_distinct", "n",
    "any", "all", "quantile", "IQR", "mad", "nth",
    "is_na", "if_else", "case_when", "case_match", "coalesce", "na_if", "between", "near",
    "lag", "lead", "row_number", "min_rank", "dense_rank", "percent_rank", "cume_dist",
    "ntile", "consecutive_id", "cumsum", "cummean", "cummin", "cummax", "cumall", "cumany",
    "desc",
    "across", "if_any", "if_all", "pick",
    # base R
    "is_in", "abs", "sqrt", "exp", "log", "log2", "log10", "floor", "ceiling", "round",
    "pmin", "pmax", "as_integer", "as_double", "as_character", "as_logical",
    # tidyselect
    "starts_with", "ends_with", "contains", "matches", "num_range",
    "everything", "last_col", "all_of", "any_of", "where",
    # predicados de tipo
    "is_numeric", "is_integer", "is_double", "is_character", "is_logical",
]
