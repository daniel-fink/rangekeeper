"""Escaped HTML and plain text over the same numeric Stream projection."""

from dataclasses import dataclass
from datetime import date, timedelta
from html import escape


def _coordinate_label(coordinate):
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


@dataclass(frozen=True)
class StreamTable:
    stream: object
    transpose: bool = False
    precision: int = 2

    def __post_init__(self):
        if type(self.transpose) is not bool:
            raise TypeError("transpose must be bool")
        if type(self.precision) is not int or not 0 <= self.precision <= 12:
            raise ValueError("precision must be an integer from 0 to 12")

    def _cells(self):
        from rangekeeper.adapters.polars import stream_projection

        batch, grid, amounts, present = stream_projection(self.stream)
        periods = [_coordinate_label(batch.coordinates[c]) for c in grid]
        lines = [
            f"{label} [{unit}]" for label, unit in zip(self.stream.labels, batch.units)
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
                            else f"{amounts[line,c]:,.{self.precision}f}"
                        )
                    )
                    for c in grid
                ]
            )
        if self.transpose:
            return ["Line item", *periods], [
                [label, *row] for label, row in zip(lines, values)
            ]
        return ["Period / date", *lines], [
            [period, *(values[line][i] for line in range(len(lines)))]
            for i, period in enumerate(periods)
        ]

    def _repr_html_(self):
        headers, rows = self._cells()
        header = (
            "<tr>" + "".join(f"<th>{escape(cell)}</th>" for cell in headers) + "</tr>"
        )
        body = "".join(
            "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
            for row in rows
        )
        return f"<table><thead>{header}</thead><tbody>{body}</tbody></table><small>— absent; ? unknown. Period end boundaries are exclusive.</small>"

    def __str__(self):
        headers, rows = self._cells()
        widths = [
            max(len(row[i]) for row in [headers, *rows]) for i in range(len(headers))
        ]
        return (
            "\n".join(
                " | ".join(cell.ljust(width) for cell, width in zip(row, widths))
                for row in [headers, *rows]
            )
            + "\n— absent; ? unknown."
        )

    def __repr__(self):
        return str(self)
