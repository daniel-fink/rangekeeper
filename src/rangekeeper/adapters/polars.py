"""Detached, lossless Flow movement tables; Polars is an optional dependency."""

from __future__ import annotations
from typing import TYPE_CHECKING
from ..model.flow import Flow, validate_flow

if TYPE_CHECKING:
    from polars import DataFrame


def to_frame(flow: Flow) -> DataFrame:
    """Export movement fields, including coordinates, periods and Claim references.

    Flow units are an explicit argument to from_frame; a table alone does not
    carry the complete domain contract. Empty tables retain their movement columns.
    """
    import polars as pl

    rows = [dict(s.to_data(), _present=list(s.field_names())) for s in flow.movements]
    if not rows:
        return pl.DataFrame(
            schema={
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
    for name in ("date", "period", "magnitude", "claims"):
        if name not in frame.columns:
            frame = frame.with_columns(pl.lit(None).alias(name))
    return frame.select("key", "date", "period", "magnitude", "claims", "_present")


def from_frame(frame: DataFrame, *, units: str) -> Flow:
    """Copy an explicit movement table; NaN is invalid rather than an alias for missing."""
    data = frame.to_dicts()
    for movement in data:
        present = movement.pop("_present")
        for field in tuple(movement):
            if field not in present:
                movement.pop(field)
    result = Flow.from_data({"units": units, "movements": data})
    validate_flow(result)
    return result
