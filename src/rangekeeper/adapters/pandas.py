"""Detached pandas access. Canonical Flow content never contains a Series/DataFrame."""

from __future__ import annotations

from datetime import date, datetime
import pandas as pd
from ..table import Table, TableError
from ..model.flow import Flow, from_events, validate_flow, resolve_date
from ..duration.period import PeriodTiming


def to_frame(flow: Flow) -> pd.DataFrame:
    """Export all movement fields; nested objects are fresh copies of canonical content."""
    import pandas as pd

    return pd.DataFrame(
        [dict(s.to_data(), _present=list(s.field_names())) for s in flow.movements],
        columns=["key", "date", "period", "magnitude", "claims", "_present"],
    ).astype(object)


def to_series(
    flow: Flow, *, name: str | None = None, timing: PeriodTiming | None = None
) -> pd.Series:
    """Project magnitudes onto dates for display; periods/Claims are omitted.

    Undated period movements require an explicit timing convention.

    This projection is deliberately not the lossless interchange route. Use
    to_frame or Model JSON when provenance and bounded-period meaning must survive.
    """
    import pandas as pd

    return pd.Series(
        [s.magnitude for s in flow.movements],
        index=[resolve_date(s, timing=timing) for s in flow.movements],
        name=name,
        dtype=object,
    )


def from_series(series, *, units: str, keys=None) -> Flow:
    """Import observations, treating pandas NA/NaN as explicitly missing movements."""
    import pandas as pd

    dates = []
    for value in series.index:
        if isinstance(value, (pd.Timestamp, datetime)):
            # pandas commonly stores a date index as naive midnight timestamps.
            # Accept that representation, but never discard time or timezone data.
            if value.tzinfo is not None or any(
                (
                    value.hour,
                    value.minute,
                    value.second,
                    value.microsecond,
                    getattr(value, "nanosecond", 0),
                )
            ):
                raise ValueError(
                    "Series index must contain dates or naive midnight timestamps"
                )
            value = value.date()
        dates.append(value)
    values = [None if pd.isna(value) else float(value) for value in series.values]
    return from_events(dates, values, units=units, keys=keys)


def from_frame(frame: pd.DataFrame, *, units: str) -> Flow:
    """Read the lossless movement-column format returned by to_frame."""
    import pandas as pd

    rows = []
    for row in frame.to_dict(orient="records"):
        movement = {key: row[key] for key in row["_present"]}
        for key in ("date", "period", "magnitude", "claims"):
            value = movement.get(key)
            if key in movement and (
                value is None or isinstance(value, float) and pd.isna(value)
            ):
                movement[key] = None
        rows.append(movement)
    result = Flow.from_data({"units": units, "movements": rows})
    validate_flow(result)
    return result


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


__all__ = [
    "from_dataframe",
    "to_dataframe",
    "to_frame",
    "from_frame",
    "to_series",
    "from_series",
]
