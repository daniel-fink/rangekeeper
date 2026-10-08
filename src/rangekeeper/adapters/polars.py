"""Detached Polars projections. Records retain identity, units and field presence."""

from __future__ import annotations
from typing import TYPE_CHECKING
from rangekeeper.model.flow import Flow
from rangekeeper.shared.table import Table
from rangekeeper.model.duration.period import PeriodTiming

if TYPE_CHECKING:
    from polars import DataFrame


def to_frame(flow: Flow | Table) -> DataFrame:
    """Export a Table or lossless Flow, retaining column and row order.

    Table metadata stays outside the display frame; opaque cells use Object columns.
    Flow columns include coordinates, periods and Claim references.

    Flow units are an explicit argument to from_frame; a table alone does not
    carry the complete domain contract. Empty tables retain their movement columns.
    """
    import polars as pl

    if isinstance(flow, Table):
        # Object columns keep opaque Python cells intact. Native homogeneous
        # scalars stay useful for Polars expressions without coercing mixed cells.
        from datetime import date, datetime

        columns = []
        for name in flow.columns:
            values = flow.column(name)
            kinds = {type(value) for value in values if value is not None}
            native = len(kinds) <= 1 and kinds <= {
                str,
                bool,
                int,
                float,
                date,
                datetime,
            }
            try:
                column = pl.Series(name, values, dtype=None if native else pl.Object)
            except OverflowError:
                # Arbitrary Python integers are valid Table cells even when they
                # exceed Polars' native integer widths.
                column = pl.Series(name, values, dtype=pl.Object)
            columns.append(column)
        return pl.DataFrame(columns)
    if not isinstance(flow, Flow):
        raise TypeError("value must be a Flow or Table")
    rows = [dict(s.to_data(), _present=list(s.field_names())) for s in flow.movements]
    if not rows:
        return pl.DataFrame(
            schema={
                "id": pl.String,
                "key": pl.String,
                "date": pl.String,
                "period": pl.Null,
                "magnitude": pl.Float64,
                "claims": pl.List(pl.String),
                "_present": pl.List(pl.String),
            }
        )
    frame = pl.DataFrame(rows, infer_schema_length=None)
    # Include omitted columns without inventing field presence in the record.
    for name in ("key", "date", "period", "magnitude", "claims"):
        if name not in frame.columns:
            frame = frame.with_columns(pl.lit(None).alias(name))
    return frame.select(
        "id", "key", "date", "period", "magnitude", "claims", "_present"
    )


def from_frame(frame: DataFrame, *, units: str) -> Flow:
    """Copy an explicit movement table; NaN is invalid rather than an alias for missing."""
    data = frame.to_dicts()
    for movement in data:
        present = movement.pop("_present")
        for field in tuple(movement):
            if field not in present:
                movement.pop(field)
    result = Flow.from_data({"units": units, "movements": data})
    result.check()
    return result


def to_table(frame: DataFrame) -> Table:
    """Copy frame cells to a Table; row identity and provenance need separate evidence."""
    return Table(columns=frame.columns, rows=frame.to_dicts())


def dates(
    flow: Flow, *, name: str = "magnitude", timing: PeriodTiming | None = None
) -> DataFrame:
    """Project dates and magnitudes for display, with an explicit period convention.

    This omits Movement IDs, matching keys, coverage and Claims. Use to_frame for interchange.
    """
    import polars as pl

    if name == "date":
        raise ValueError("magnitude column must differ from date")
    return pl.DataFrame(
        {
            "date": pl.Series(
                [m.resolve(timing=timing) for m in flow.movements], dtype=pl.Date
            ),
            name: pl.Series([m.magnitude for m in flow.movements], dtype=pl.Float64),
        }
    )
