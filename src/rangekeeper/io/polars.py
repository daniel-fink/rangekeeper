"""Detached Polars projections. Records retain identity, units and field presence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rangekeeper.duration.period import PeriodTiming
from rangekeeper.flow import Flow, Stream
from rangekeeper.shared.optional import requires
from rangekeeper.shared.table import Table

if TYPE_CHECKING:
    from polars import DataFrame


def to_frame(flow: Flow | Stream | Table) -> DataFrame:
    """Export a Table or lossless Flow, retaining column and row order.

    Table metadata stays outside the display frame; opaque cells use Object columns.
    Flow columns are the Movement slots in schema order, then _present. Their
    types come from the schema slots. Integer magnitudes stay integers.

    Flow units are an explicit argument to from_frame; a table alone does not
    carry the complete domain contract. Empty tables retain their movement columns.
    """
    with requires("calculations"):
        import polars as pl

    if isinstance(flow, Stream):
        return stream_frame(flow)
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
    rows = [s.to_data() for s in flow.movements]
    # Omitted fields become null cells; _present keeps the record's field presence.
    columns = [
        _movement_column(pl, name, slot, [row.get(name) for row in rows])
        for name, slot in _movement_slots()
    ]
    present = [list(s.field_names()) for s in flow.movements]
    columns.append(pl.Series("_present", present, dtype=pl.List(pl.String)))
    return pl.DataFrame(columns)


def _movement_slots():
    """Return the Movement slots in schema order.

    slots.json sorts slot names, so the order comes from the generated
    constructor, which declares the fields in schema order.
    """
    import inspect

    from rangekeeper.schema.records import Movement as MovementRecord
    from rangekeeper.schema.validation import slots_for

    slots = slots_for("Movement")
    names = inspect.signature(MovementRecord.__init__).parameters
    return [(name, slots[name]) for name in names if name != "self"]


def _movement_column(pl, name, slot, values):
    """Return one Movement column with the Polars type of its schema slot.

    UUIDs, strings and dates keep their wire text. A record column is a Struct
    (Null when no row has a value). A numerical column keeps Python numbers:
    Int64 when all values are integers, Float64 when all are floats, and an
    Object column when the values mix integers and floats or exceed Int64.
    """
    (option,) = slot["options"]
    category, kind = option["category"], option["kind"]
    if category == "record":
        if all(value is None for value in values):
            return pl.Series(name, values, dtype=pl.Null)
        rows = [{name: value} for value in values]
        return pl.DataFrame(rows, infer_schema_length=None).to_series()
    if category == "primitive" and kind in ("decimal", "double", "float", "integer"):
        kinds = {type(value) for value in values if value is not None}
        dtype = pl.Int64 if kinds == {int} else pl.Float64 if kinds <= {float} else None
        try:
            return pl.Series(name, values, dtype=dtype or pl.Object)
        except (OverflowError, TypeError):
            # Python integers can exceed the native Polars integer widths.
            return pl.Series(name, values, dtype=pl.Object)
    if category != "uuid" and (category, kind) not in (
        ("primitive", "string"),
        ("primitive", "date"),
    ):
        raise TypeError(f"Movement.{name}: unsupported slot for a Polars column")
    dtype = pl.List(pl.String) if slot["many"] else pl.String
    return pl.Series(name, values, dtype=dtype)


def from_frame(frame: DataFrame, *, units: str) -> Flow:
    """Copy an explicit movement table; NaN is invalid rather than an alias for missing."""
    data = frame.to_dicts()
    for movement in data:
        present = movement.pop("_present")
        for field in tuple(movement):
            if field not in present:
                movement.pop(field)
    result = Flow.from_data({"units": units, "movements": data})
    return result


def to_table(frame: DataFrame) -> Table:
    """Copy frame cells to a Table; row identity and provenance need separate evidence."""
    return Table(columns=frame.columns, rows=frame.to_dicts())


def dates(
    flow: Flow, *, name: str = "magnitude", timing: PeriodTiming | None = None
) -> DataFrame:
    """Project dates and magnitudes for display, with an explicit period convention.

    This omits Movement IDs, matching keys, coverage and Claims. Magnitudes are
    Float64, so integers become floats. Use to_frame for interchange.
    """
    with requires("calculations"):
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


def stream_projection(stream):
    """One projection for numeric export and both presentation forms."""
    batch = stream._prepared()
    try:
        grid = batch.grid(stream.join)
    except ValueError as error:
        raise ValueError(f"{error}; lines: {', '.join(stream.names)}") from error
    amounts = {}
    present = set()
    for line, coordinate, magnitude in batch.frame.select(
        "line", "coordinate", "magnitude"
    ).iter_rows():
        amounts[line, coordinate] = magnitude
        present.add((line, coordinate))
    return batch, grid, amounts, present


def stream_frame(stream) -> DataFrame:
    """Export numeric line columns and explicit coordinates, without mutable shared state.

    Line columns are Float64 numerical projections, not lossless records.
    """
    from datetime import date

    from rangekeeper.flow._batch import polars

    pl = polars()
    batch, grid, amounts, _ = stream_projection(stream)
    reserved = {"date", "period_start", "period_end", "key"}
    if reserved & set(stream.names):
        raise ValueError(
            "line names conflict with coordinate column names; select explicit names"
        )
    coordinates = [batch.coordinates[i] for i in grid]
    frame = pl.DataFrame(
        {
            "date": pl.Series(
                [
                    (
                        date.fromisoformat(c[1])
                        if c[0] == "event"
                        else date.fromisoformat(c[3])
                        if c[3]
                        else None
                    )
                    for c in coordinates
                ],
                dtype=pl.Date,
            ),
            "period_start": pl.Series(
                [
                    date.fromisoformat(c[1]) if c[0] == "period" else None
                    for c in coordinates
                ],
                dtype=pl.Date,
            ),
            "period_end": pl.Series(
                [
                    date.fromisoformat(c[2]) if c[0] == "period" else None
                    for c in coordinates
                ],
                dtype=pl.Date,
            ),
            "key": pl.Series(
                [c[2] if c[0] == "event" else None for c in coordinates],
                dtype=pl.String,
            ),
        }
    )
    return frame.with_columns(
        [
            pl.Series(label, [amounts.get((line, c)) for c in grid], dtype=pl.Float64)
            for line, label in enumerate(stream.names)
        ]
    ).clone()


def text_frame(table: Table):
    """Project scalar cells to text without mixed-column numeric rounding.

    Use the returned Polars frame for CSV or other textual exports. Rich and
    non-finite cells require an explicit caller encoding. Row IDs stay separate.
    """
    with requires("calculations"):
        import polars as pl

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
    return pl.DataFrame(columns)


def _scalar(
    value: object,
    row_index: int,
    column: str,
) -> str | None:
    if value is None:
        return None
    import math
    from numbers import Real
    from uuid import UUID

    from rangekeeper.shared.errors import EncodingError

    if isinstance(value, (str, bool, UUID, int)):
        return str(value)
    if isinstance(value, Real) and math.isfinite(float(value)):
        return str(value)
    raise EncodingError(
        f"Text projection row {row_index} column {column!r} has unsupported value type "
        f"{type(value).__name__}"
    )
