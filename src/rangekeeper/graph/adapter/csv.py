from __future__ import annotations

import math
from numbers import Real
from os import PathLike
from pathlib import Path

import pandas as pd

from ..table import Table
from .errors import AdapterEncodingError
from .pandas import from_dataframe, to_dataframe


__all__ = ["read", "write"]


def write(table: Table, path: str | PathLike[str]) -> Path:
    """Write an ordinary, intentionally textual CSV projection."""
    if not isinstance(table, Table):
        raise TypeError("table must be a Table")
    for row_index, row in enumerate(table.rows):
        for column in table.columns:
            _validate_csv_scalar(row[column], row_index, column)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    to_dataframe(table).to_csv(
        target,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )
    return target


def read(path: str | PathLike[str]) -> Table:
    """Read a CSV through pandas and convert the resulting DataFrame to a Table."""
    return from_dataframe(pd.read_csv(Path(path)))


def _validate_csv_scalar(
    value: object,
    row_index: int,
    column: str,
) -> object:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Real) and math.isfinite(float(value)):
        return value
    raise AdapterEncodingError(
        f"CSV row {row_index} column {column!r} has unsupported value type "
        f"{type(value).__name__}"
    )
