"""Stream tables: one projection for numeric export and for display.

``Stream.to_frame()`` and ``Stream.display()`` use this module, and
``rangekeeper.io.polars`` exports Streams through it. It needs the
``calculations`` extra (Polars) and no chart or graph dependency.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from rangekeeper.flow._batch import Batch, polars
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError

if TYPE_CHECKING:
    from polars import DataFrame

    from rangekeeper.flow.stream import Stream

__all__ = ["StreamTable"]

# The amount of each line at each coordinate, by (line, coordinate) index.
type _Amounts = dict[tuple[int, int], float | None]


def stream_projection(
    stream: Stream,
) -> tuple[Batch, tuple[int, ...], _Amounts, set[tuple[int, int]]]:
    """One projection for numeric export and both presentation forms."""
    batch = stream._prepared()
    try:
        grid = batch.grid(stream.join)
    except ContractError as error:
        raise type(error)(
            f"{error}; lines: {', '.join(stream.names)}",
            code=error.code,
            values={**error.values, "lines": list(stream.names)},
        ) from error
    amounts: _Amounts = {}
    present: set[tuple[int, int]] = set()
    for line, coordinate, magnitude in batch.frame.select(
        "line", "coordinate", "magnitude"
    ).iter_rows():
        amounts[line, coordinate] = magnitude
        present.add((line, coordinate))
    return batch, grid, amounts, present


def stream_frame(stream: Stream) -> DataFrame:
    """Export numeric line columns and explicit coordinates, without mutable shared state.

    Line columns are Float64 numerical projections, not lossless records.
    """
    pl = polars()
    batch, grid, amounts, _ = stream_projection(stream)
    reserved = {"date", "period_start", "period_end", "key"}
    if reserved & set(stream.names):
        raise ContractError(
            "line names conflict with coordinate column names; select explicit names",
            code=Code.UNIQUE,
            values={"names": sorted(reserved & set(stream.names))},
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


def _coordinate_label(coordinate: tuple) -> str:
    """Return the row or column label of one coordinate."""
    if coordinate[0] == "event":
        return coordinate[1] + (f" [{coordinate[2]}]" if coordinate[2] else "")
    start, end = date.fromisoformat(coordinate[1]), date.fromisoformat(coordinate[2])
    if (
        start.month == start.day == end.month == end.day == 1
        and end.year == start.year + 1
    ):
        label = str(start.year)
    elif (
        start.day == end.day == 1
        and (end.year * 12 + end.month) - (start.year * 12 + start.month) == 1
    ):
        label = start.strftime("%b %Y")
    else:
        label = f"{start.isoformat()} to {end.isoformat()} (exclusive)"
    if coordinate[3]:
        label += f" · dated {coordinate[3]}"
    return label


def render(headers: Sequence[str], rows: Sequence[Sequence[str]], *, html: bool) -> str:
    """Render prepared string cells as a native Polars table, in HTML or text."""
    pl = polars()
    frame = pl.DataFrame(
        rows,
        # Object cells let Polars display the prepared strings without the
        # literal quotation marks its HTML renderer adds to String columns.
        schema=[(header, pl.Object) for header in headers],
        orient="row",
    )
    # Display strings preserve missing states and precision without changing
    # numeric exports. Scope the native renderer's settings to this call.
    with pl.Config(
        tbl_hide_column_names=False,
        tbl_hide_column_data_types=True,
        tbl_hide_dataframe_shape=True,
        tbl_rows=-1,
        tbl_cols=-1,
        tbl_width_chars=-1,
        fmt_str_lengths=max(len(cell) for row in [headers, *rows] for cell in row),
    ):
        return frame._repr_html_() if html else str(frame)


@dataclass(frozen=True, kw_only=True)
class StreamTable:
    """Rows by period or event date, one column per line item, with units.

    "—" marks a cell with no Movement. "?" marks a Movement with no magnitude.
    ``transpose`` puts the line items in rows.
    """

    stream: Stream
    transpose: bool = False
    precision: int = 2

    def __post_init__(self) -> None:
        if type(self.transpose) is not bool:
            raise TypeError("transpose must be bool")
        if type(self.precision) is not int:
            raise TypeError("precision must be an int")
        if not 0 <= self.precision <= 12:
            raise ContractError(
                "precision must be an integer from 0 to 12",
                values={"precision": self.precision},
            )

    def _cells(self) -> tuple[list[str], list[list[str]]]:
        """Return the headers and the rows of display strings."""
        batch, grid, amounts, present = stream_projection(self.stream)
        periods = [_coordinate_label(batch.coordinates[c]) for c in grid]
        lines = [
            f"{label} [{unit}]"
            for label, unit in zip(self.stream.names, batch.units, strict=True)
        ]
        values = []
        for line in range(len(lines)):
            values.append(
                [
                    (
                        "—"
                        if (line, c) not in present
                        else (
                            "?"
                            if amounts[line, c] is None
                            else f"{amounts[line, c]:,.{self.precision}f}"
                        )
                    )
                    for c in grid
                ]
            )
        if self.transpose:
            return ["Line item", *periods], [
                [label, *row] for label, row in zip(lines, values, strict=True)
            ]
        return ["Period / date", *lines], [
            [period, *(values[line][i] for line in range(len(lines)))]
            for i, period in enumerate(periods)
        ]

    def _render(self, *, html: bool) -> str:
        return render(*self._cells(), html=html)

    def _repr_html_(self) -> str:
        return self._render(html=True)

    def __str__(self) -> str:
        return self._render(html=False)

    def __repr__(self) -> str:
        return str(self)
