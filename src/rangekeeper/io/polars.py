"""Detached Polars projections. Records retain identity, units and field presence.

``to_frame`` and ``from_frame`` make a lossless round trip of a Flow, and
``to_table`` copies a frame to a Table. ``dates`` and ``text_frame`` are
display and text projections. Install ``rangekeeper[calculations]``.
"""

from __future__ import annotations

import inspect
import math
from datetime import date, datetime
from numbers import Real
from typing import TYPE_CHECKING, Any
from uuid import UUID

from rangekeeper.duration import PeriodTiming
from rangekeeper.flow import Flow, Stream
from rangekeeper.money import is_currency
from rangekeeper.schema.records import Movement as MovementRecord
from rangekeeper.schema.validation import slots_for
from rangekeeper.shared.amounts import encoded, number
from rangekeeper.shared.errors import ContractError, EncodingError
from rangekeeper.shared.optional import requires
from rangekeeper.shared.table import Table

if TYPE_CHECKING:
    from polars import DataFrame, Series

__all__ = ["dates", "from_frame", "text_frame", "to_frame", "to_table"]


def _polars() -> Any:
    """Import Polars, the optional dependency of these projections."""
    with requires("calculations"):
        import polars  # noqa: PLC0415 - optional dependency

    return polars


def to_frame(value: Flow | Stream | Table) -> DataFrame:
    """Export a Flow, a Stream or a Table, retaining column and row order.

    A Flow frame is lossless: its columns are the Movement slots in schema
    order, then ``_present``. Their types come from the schema slots. Integer
    magnitudes stay integers; currency amounts are Float64 (ADR-023), and
    ``from_frame`` converts them back. Flow units are an explicit argument to
    ``from_frame``; a table alone does not carry the complete domain contract.
    Empty Flows keep their Movement columns.

    A Stream frame is the numerical projection of ``Stream.to_frame``.

    A Table frame keeps the Table metadata outside the frame; opaque cells use
    Object columns.
    """
    if isinstance(value, Stream):
        return value.to_frame()
    if isinstance(value, Table):
        return _table_frame(value)
    if isinstance(value, Flow):
        return _flow_frame(value)
    raise TypeError("value must be a Flow, a Stream or a Table")


def _table_frame(table: Table) -> DataFrame:
    """Return the frame of a Table; mixed or opaque cells use Object columns."""
    pl = _polars()
    # Object columns keep opaque Python cells intact. Native homogeneous
    # scalars stay useful for Polars expressions without coercing mixed cells.
    native_types = {str, bool, int, float, date, datetime}
    columns = []
    for name in table.columns:
        values = table.column(name)
        kinds = {type(value) for value in values if value is not None}
        native = len(kinds) <= 1 and kinds <= native_types
        try:
            column = pl.Series(name, values, dtype=None if native else pl.Object)
        except OverflowError:
            # Arbitrary Python integers are valid Table cells even when they
            # exceed Polars' native integer widths.
            column = pl.Series(name, values, dtype=pl.Object)
        columns.append(column)
    return pl.DataFrame(columns)


def _flow_frame(flow: Flow) -> DataFrame:
    """Return the lossless frame of a Flow: one column for each Movement slot."""
    pl = _polars()
    rows = [s.to_data() for s in flow.movements]
    # Omitted fields become null cells; _present keeps the record's field presence.
    columns = [
        _movement_column(name, slot, [row.get(name) for row in rows])
        for name, slot in _movement_slots()
    ]
    present = [list(s.field_names()) for s in flow.movements]
    columns.append(pl.Series("_present", present, dtype=pl.List(pl.String)))
    return pl.DataFrame(columns)


def _movement_slots() -> list[tuple[str, dict[str, Any]]]:
    """Return the Movement slots in schema order.

    slots.json sorts slot names, so the order comes from the generated
    constructor, which declares the fields in schema order.
    """
    slots = slots_for("Movement")
    names = inspect.signature(MovementRecord.__init__).parameters
    return [(name, slots[name]) for name in names if name != "self"]


def _movement_column(name: str, slot: dict[str, Any], values: list[Any]) -> Series:
    """Return one Movement column with the Polars type of its schema slot.

    UUIDs, strings and dates keep their wire text. A record column is a Struct
    (Null when no row has a value). A numerical column keeps Python numbers:
    Int64 when all values are integers, Float64 when all are floats, and an
    Object column when the values mix integers and floats or exceed Int64. A
    currency amount is a float64 from ``money.to_number``.
    """
    pl = _polars()
    kinds = {option["kind"] for option in slot["options"]}
    category, kind = slot["options"][0]["category"], slot["options"][0]["kind"]
    if category == "record":
        if all(value is None for value in values):
            return pl.Series(name, values, dtype=pl.Null)
        rows = [{name: value} for value in values]
        return pl.DataFrame(rows, infer_schema_length=None).to_series()
    if category == "primitive" and kinds & {"Amount", "double", "float", "integer"}:
        # A currency amount becomes its float64 (ADR-023).
        values = [number(value) for value in values]
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


def from_frame(*, frame: DataFrame, units: str) -> Flow:
    """Copy an explicit movement table; NaN is invalid rather than an alias for missing.

    With currency units, each magnitude becomes an amount through
    ``money.to_amount`` (ADR-023).
    """
    data = frame.to_dicts()
    currency = is_currency(units)
    for movement in data:
        present = movement.pop("_present")
        for field in tuple(movement):
            if field not in present:
                movement.pop(field)
        if currency and movement.get("magnitude") is not None:
            movement["magnitude"] = encoded(movement["magnitude"])
    return Flow.from_data({"units": units, "movements": data})


def to_table(frame: DataFrame) -> Table:
    """Copy frame cells to a Table; row identity and provenance need separate evidence."""
    return Table(columns=frame.columns, rows=frame.to_dicts())


def dates(
    *,
    flow: Flow,
    name: str = "magnitude",
    timing: PeriodTiming | None = None,
) -> DataFrame:
    """Project dates and magnitudes for display, with an explicit period convention.

    This omits Movement IDs, matching keys, coverage and Claims. Magnitudes are
    Float64, so integers become floats. Use to_frame for interchange. A
    magnitude column with the name ``date`` raises ``ContractError``.
    """
    pl = _polars()
    if name == "date":
        raise ContractError(
            "the magnitude column must not have the name 'date'",
            values={"name": name},
        )
    return pl.DataFrame(
        {
            "date": pl.Series(
                [m.resolve(timing=timing) for m in flow.movements], dtype=pl.Date
            ),
            name: pl.Series(
                [None if m.magnitude is None else m.number for m in flow.movements],
                dtype=pl.Float64,
            ),
        }
    )


def text_frame(table: Table) -> DataFrame:
    """Project scalar cells to text without mixed-column numeric rounding.

    Use the returned Polars frame for CSV or other textual exports. Rich and
    non-finite cells require an explicit caller encoding. Row IDs stay separate.
    """
    pl = _polars()
    if not isinstance(table, Table):
        raise TypeError("table must be a Table")
    # Serialize cells as text before dataframe construction. Inferring a shared
    # numeric dtype here could round large integers in mixed numeric columns.
    columns = {
        column: pl.Series(
            column,
            [
                _scalar(value, row=row, column=column)
                for row, value in enumerate(table.column(column))
            ],
            dtype=pl.String,
        )
        for column in table.columns
    }
    return pl.DataFrame(columns)


def _scalar(value: object, *, row: int, column: str) -> str | None:
    """Return the text of one scalar cell; raise EncodingError for another value."""
    if value is None:
        return None
    if isinstance(value, (str, bool, UUID, int)):
        return str(value)
    if isinstance(value, Real) and math.isfinite(float(value)):
        return str(value)
    raise EncodingError(
        f"Text projection row {row} column {column!r} has unsupported value type "
        f"{type(value).__name__}"
    )
