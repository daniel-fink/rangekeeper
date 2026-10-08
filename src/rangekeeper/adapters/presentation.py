"""Native Polars display over a detached, formatted Stream projection."""

from dataclasses import dataclass
from datetime import date


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

    def _render(self, *, html: bool):
        from rangekeeper.calculations._batch import polars

        pl = polars()
        headers, rows = self._cells()
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

    def _repr_html_(self):
        return self._render(html=True)

    def __str__(self):
        return self._render(html=False)

    def __repr__(self):
        return str(self)
