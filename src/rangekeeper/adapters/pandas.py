from __future__ import annotations

import pandas as pd

from ..table import Table, TableError

__all__ = ["from_dataframe", "to_dataframe"]


def to_dataframe(table: Table) -> pd.DataFrame:
    """Create a DataFrame while preserving Table column and row order."""
    if not isinstance(table, Table):
        raise TypeError("table must be a Table")
    return pd.DataFrame.from_records(
        (dict(row.values) for row in table.rows),
        columns=table.columns,
    )


def from_dataframe(frame: pd.DataFrame) -> Table:
    """Create a Table from DataFrame columns, excluding the DataFrame index."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    columns = tuple(frame.columns)
    if len(columns) != len(set(columns)):
        raise TableError("DataFrame columns must be unique")
    columns = Table(columns=columns, rows=()).columns
    return Table(
        columns=columns,
        rows=tuple(
            {column: record[column] for column in columns}
            for record in frame.to_dict(orient="records")
        ),
    )
