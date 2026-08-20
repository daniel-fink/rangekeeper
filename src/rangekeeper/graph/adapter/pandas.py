from __future__ import annotations

import pandas as pd

from ..materialization import Table


def to_dataframe(table: Table) -> pd.DataFrame:
    """Create a DataFrame while preserving Table column and row order."""
    if not isinstance(table, Table):
        raise TypeError("table must be a Table")
    return pd.DataFrame.from_records(
        (dict(row) for row in table.rows),
        columns=table.columns,
    )


def from_dataframe(frame: pd.DataFrame) -> Table:
    """Create a Table from DataFrame columns, excluding the DataFrame index."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    columns = tuple(frame.columns)
    if len(columns) != len(set(columns)):
        raise ValueError("DataFrame columns must be unique")
    return Table(
        columns=columns,
        rows=tuple(frame.to_dict(orient="records")),
    )
