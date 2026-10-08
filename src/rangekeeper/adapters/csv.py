from __future__ import annotations

import math
from numbers import Real
from os import PathLike
from pathlib import Path
from uuid import UUID

import polars as pl

from rangekeeper.shared.table import Table
from rangekeeper.shared.errors import EncodingError
from rangekeeper.adapters.polars import to_table

__all__ = ["read", "write"]


def write(table: Table, path: str | PathLike[str]) -> Path:
    """Write a textual projection. UUID cells become text; no Model reconstruction."""
    if not isinstance(table, Table):
        raise TypeError("table must be a Table")
    # Serialize cells as text before dataframe construction. Inferring a shared
    # numeric dtype here could round large integers in mixed numeric columns.
    columns = {
        column: pl.Series(
            column,
            [
                _scalar(value, row_index, column)
                for row_index, value in enumerate(table.column(column))
            ],
            dtype=pl.String,
        )
        for column in table.columns
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(columns).write_csv(target)
    return target


def read(path: str | PathLike[str], *, schema_overrides=None) -> Table:
    """Read a textual Table using Polars type inference.

    Empty fields become None; strings such as NA remain text. CSV does not
    preserve identifiers with leading zeros unless schema_overrides is supplied.
    """
    return to_table(
        pl.read_csv(
            Path(path), schema_overrides=schema_overrides, infer_schema_length=None
        )
    )


def _scalar(
    value: object,
    row_index: int,
    column: str,
) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, bool, UUID, int)):
        return str(value)
    if isinstance(value, Real) and math.isfinite(float(value)):
        return str(value)
    raise EncodingError(
        f"CSV row {row_index} column {column!r} has unsupported value type "
        f"{type(value).__name__}"
    )
