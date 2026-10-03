"""Ordered, domain-independent tables. Cells are unconstrained and shallowly frozen."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID


class TableError(ValueError):
    """Invalid table columns, row shape, or duplicate row identity."""


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


@dataclass(frozen=True, slots=True, init=False)
class Table:
    """Ordered Rows with optional identity and unconstrained cell values.

    Construction accepts plain mappings as unidentified rows. Cell access is
    through row.values; identity is metadata and never an implicit column.
    """

    columns: tuple[str, ...]
    rows: tuple[Row, ...]

    def __init__(
        self,
        columns: Iterable[str],
        rows: Iterable[Row | Mapping[str, object]],
    ) -> None:
        columns = _validate_names(columns, "columns")
        normalized_rows = []
        identities = set()
        for item in rows:
            row = item if isinstance(item, Row) else Row(values=item)
            missing = tuple(column for column in columns if column not in row.values)
            extra = tuple(column for column in row.values if column not in columns)
            if missing or extra:
                raise TableError(
                    "row columns do not match Table columns: "
                    f"missing={list(missing)!r}, extra={list(extra)!r}"
                )
            if row.id is not None:
                if row.id in identities:
                    raise TableError("Row IDs must be unique")
                identities.add(row.id)
            normalized_rows.append(
                Row(
                    values={column: row.values[column] for column in columns}, id=row.id
                )
            )
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "rows", tuple(normalized_rows))

    def row(self, row_id: UUID) -> Row:
        """Return an identified Row; unidentified rows do not match any key."""
        if not isinstance(row_id, UUID):
            raise TypeError("row_id must be UUID")
        for row in self.rows:
            if row.id == row_id:
                return row
        raise KeyError(row_id)

    def column(self, name: str) -> tuple[object, ...]:
        """Return one column in row order."""

        if name not in self.columns:
            raise KeyError(name)
        return tuple(row.values[name] for row in self.rows)


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
