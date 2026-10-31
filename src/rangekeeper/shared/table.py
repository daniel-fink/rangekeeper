"""Ordered, domain-independent tables. Cells are unconstrained and shallowly frozen.

A notebook shows a Table as an HTML table (``_repr_html_``); its ``repr`` gives
its shape and column names.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import get_close_matches
from enum import Enum
from html import escape
from types import MappingProxyType
from typing import TypeGuard
from uuid import UUID

from rangekeeper.shared.errors import ContractError, MissingReferenceError, TableError


@dataclass(frozen=True, slots=True)
class Row:
    """Cell values bundled with optional identity; values are shallowly frozen."""

    values: Mapping[str, object]
    id: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.values, Mapping):
            raise TypeError("Row values must be a mapping")
        _validate_names(self.values, "Row columns")
        if self.id is not None and not isinstance(self.id, UUID):
            raise TypeError("Row id must be a UUID or None")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Table:
    """Ordered Rows with optional identity and unconstrained cell values.

    Construction accepts plain mappings as unidentified rows. Cell access is
    through row.values; identity is metadata and never an implicit column.

    A notebook shows the first 50 rows as an HTML table, then the number of
    the other rows. When each cell of a column is a Quantity in the same units,
    the header gives the units and the cells give the magnitudes. A UUID cell
    that identifies another row shows that row's ``key``, ``name`` or ``code``;
    another UUID shows its first eight digits.
    """

    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    _rows_by_id: Mapping[UUID, Row] = field(init=False, repr=False, compare=False)

    def __init__(
        self,
        columns: Iterable[str],
        rows: Iterable[Row | Mapping[str, object]],
    ) -> None:
        columns = _validate_names(columns, "columns")
        normalized_rows = []
        identities = {}
        for item in rows:
            values = item.values if isinstance(item, Row) else item
            if not isinstance(values, Mapping):
                raise TypeError("Row values must be a mapping")
            ordered = tuple(values) == columns
            if not ordered:
                _validate_names(values, "Row columns")
            missing = tuple(column for column in columns if column not in values)
            extra = tuple(column for column in values if column not in columns)
            if missing or extra:
                raise TableError(
                    "row columns do not match Table columns: "
                    f"missing={list(missing)!r}, extra={list(extra)!r}"
                )
            if isinstance(item, Row) and ordered:
                row = item
            else:
                row = Row(
                    {column: values[column] for column in columns},
                    item.id if isinstance(item, Row) else None,
                )
            if row.id is not None:
                if row.id in identities:
                    raise TableError("Row IDs must be unique")
                identities[row.id] = row
            normalized_rows.append(row)
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "rows", tuple(normalized_rows))
        object.__setattr__(self, "_rows_by_id", MappingProxyType(identities))

    def row(self, row_id: UUID) -> Row:
        """Return an identified Row; unidentified rows do not match any key.

        An unknown UUID raises ``MissingReferenceError``.
        """
        if not isinstance(row_id, UUID):
            raise TypeError("row_id must be UUID")
        try:
            return self._rows_by_id[row_id]
        except KeyError:
            raise MissingReferenceError(row_id, kind="row", where="Table") from None

    def column(self, name: str) -> tuple[object, ...]:
        """Return one column in row order.

        An unknown name raises ``MissingReferenceError`` with the nearest names.
        """
        if name not in self.columns:
            raise MissingReferenceError(
                name,
                kind="column",
                by="name",
                where="Table",
                candidates=get_close_matches(str(name), self.columns, n=3),
            )
        return tuple(row.values[name] for row in self.rows)

    def head(self, *, count: int = 5) -> Table:
        """Return a Table of the first ``count`` rows, with the same columns.

        A count below zero raises ``ContractError``.
        """
        if type(count) is not int:
            raise TypeError("count must be an int")
        if count < 0:
            raise ContractError(
                f"count must not be negative, not {count}", values={"count": count}
            )
        return Table(self.columns, self.rows[:count])

    def __repr__(self) -> str:
        names = ", ".join(self.columns[:_NAMED_COLUMNS])
        if len(self.columns) > _NAMED_COLUMNS:
            names += f", ... {len(self.columns) - _NAMED_COLUMNS} more"
        shape = ", ".join(
            (_count(len(self.rows), "row"), _count(len(self.columns), "column"))
        )
        return f"Table({shape}: {names})" if names else f"Table({shape})"

    def _repr_html_(self) -> str:
        """Return an HTML table of the first rows, for a notebook."""
        return _html(self)


_SHOWN_ROWS = 50
"""The rows of a notebook display; one more line gives the number of the others."""
_NAMED_COLUMNS = 8
"""The column names that ``repr`` gives; it counts the others."""
_LABELS = ("key", "name", "code")
"""The columns that can label a row, in order of preference."""
_SIGNIFICANT = 6
"""The significant digits of a float in a notebook display."""

type _Number = Decimal | float | int
type _Measure = tuple[_Number, str]


def _html(table: Table) -> str:
    """Return the HTML of the first rows of ``table``, then the number of the others."""
    shown = table.rows[:_SHOWN_ROWS]
    labels = _row_labels(table)
    columns = [_column(name, rows=shown, labels=labels) for name in table.columns]
    head = "".join(f"<th>{escape(header)}</th>" for header, _ in columns)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{escape(cells[index])}</td>" for _, cells in columns)
        + "</tr>"
        for index in range(len(shown))
    )
    hidden = len(table.rows) - len(shown)
    foot = (
        f'<tfoot><tr><td colspan="{max(len(columns), 1)}">'
        f"… {_count(hidden, 'more row')}</td></tr></tfoot>"
        if hidden
        else ""
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody>{foot}</table>"


def _row_labels(table: Table) -> dict[UUID, str]:
    """Return the key, name or code of each identified row, if no other row has it."""
    column = next((name for name in _LABELS if name in table.columns), None)
    if column is None:
        return {}
    found = {
        row.id: str(row.values[column])
        for row in table.rows
        if row.id is not None and row.values[column] is not None
    }
    counts = Counter(found.values())
    return {identity: label for identity, label in found.items() if counts[label] == 1}


def _column(
    name: str,
    *,
    rows: Sequence[Row],
    labels: Mapping[UUID, str],
) -> tuple[str, list[str]]:
    """Return the header and the cell texts of one column.

    When each cell with a value is a Quantity in the same units, the header
    gives the units and the cells give the magnitudes.
    """
    cells = [row.values[name] for row in rows]
    measures = [_measure(cell) for cell in cells]
    units = {measure[1] for measure in measures if measure is not None}
    measured = all(
        measure is not None
        for cell, measure in zip(cells, measures, strict=True)
        if cell is not None
    )
    if measured and len(units) == 1:
        name = f"{name} [{units.pop()}]"
        cells = [None if measure is None else measure[0] for measure in measures]
    return name, [
        _text(cell, labels=labels, row=row.id)
        for cell, row in zip(cells, rows, strict=True)
    ]


def _measure(cell: object) -> _Measure | None:
    """Return the magnitude and units of a Quantity, or None for another value.

    The Quantity types belong to higher layers, so the display reads their
    ``magnitude`` and ``units``.
    """
    magnitude = getattr(cell, "magnitude", None)
    units = getattr(cell, "units", None)
    if isinstance(units, str) and _is_number(magnitude):
        return magnitude, units
    return None


def _is_number(value: object) -> TypeGuard[_Number]:
    return isinstance(value, (Decimal, float, int)) and not isinstance(value, bool)


def _text(value: object, *, labels: Mapping[UUID, str], row: UUID | None) -> str:
    """Return the display text of one cell of the row ``row``."""
    if value is None:
        return "—"
    if isinstance(value, UUID):
        label = labels.get(value) if value != row else None
        return f"{str(value)[:8]}…" if label is None else label
    if isinstance(value, Enum):
        return value.value if isinstance(value.value, str) else value.name
    measure = _measure(value)
    if measure is not None:
        return f"{_number(measure[0])} {measure[1]}"
    return _number(value) if _is_number(value) else str(value)


def _number(value: _Number) -> str:
    """Return a number with digit groups; a float keeps six significant digits."""
    if isinstance(value, float):
        return _float(value)
    if isinstance(value, int):
        return f"{value:,}"
    return _trim(f"{value:,f}")


def _float(value: float) -> str:
    """Return a float rounded to six significant digits, or to a whole number."""
    if value == 0 or not math.isfinite(value):
        return "0" if value == 0 else str(value)
    exponent = math.floor(math.log10(abs(value)))
    if abs(exponent) > 15:
        return f"{value:.{_SIGNIFICANT}g}"
    return _trim(f"{value:,.{max(0, _SIGNIFICANT - 1 - exponent)}f}")


def _trim(text: str) -> str:
    """Remove the trailing zeros of a decimal fraction."""
    return text.rstrip("0").rstrip(".") if "." in text else text


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


def _validate_names(values: Iterable[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field} must be an iterable of strings, not a string")
    materialized = tuple(values)
    if not all(isinstance(value, str) and value.strip() for value in materialized):
        raise TableError(f"{field} must contain only non-empty strings")
    if len(materialized) != len(set(materialized)):
        raise TableError(f"{field} must not contain duplicates")
    return materialized


__all__ = ["Row", "Table", "TableError"]
