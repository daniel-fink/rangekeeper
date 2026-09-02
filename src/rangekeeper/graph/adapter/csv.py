from __future__ import annotations

import math
from os import PathLike
from pathlib import Path

import pandas as pd

from ..table import Table
from .errors import AdapterEncodingError
from .pandas import from_dataframe, to_dataframe


CsvScalar = str | int | float | bool | None


def write(table: Table, path: str | PathLike[str]) -> None:
    """Write an ordinary, intentionally textual CSV projection."""
    if not isinstance(table, Table):
        raise TypeError("table must be a Table")
    for row_index, row in enumerate(table.rows):
        for column in table.columns:
            _validate_csv_scalar(row[column], row_index, column)
    to_dataframe(table).to_csv(
        Path(path),
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )


def read(path: str | PathLike[str]) -> Table:
    """Read a CSV through pandas and convert the resulting DataFrame to a Table."""
    return from_dataframe(pd.read_csv(Path(path)))


def _validate_csv_scalar(
    value: object,
    row_index: int,
    column: str,
) -> CsvScalar:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise AdapterEncodingError(
        f"CSV row {row_index} column {column!r} has unsupported value type "
        f"{type(value).__name__}"
    )
