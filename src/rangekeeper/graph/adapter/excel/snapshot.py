"""Immutable Excel-native observations; no openpyxl objects escape the reader."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields, replace
from types import MappingProxyType

from .... import validate
from ...provenance import Location, Source
from .. import _structured
from ..document import (
    TEXT_PREVIEW_LIMIT,
    ContentItem,
    Description,
    Document,
    Inspection,
)
from ..ingestion._encoding import encode
from ..operation import _Failure
from ._coordinates import MAX_COLUMN, MAX_ROW, address, merged_bounds


def _short(value: object) -> object:
    if type(value) is str and len(value) > TEXT_PREVIEW_LIMIT:
        return value[: TEXT_PREVIEW_LIMIT - 1] + "…"
    if type(value) is tuple:
        return tuple(_short(item) for item in value)
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class Cell:
    location: Location
    raw: object = None
    formula: str | None = None
    cached: object = None
    cache_present: bool = False
    data_type: str = "n"
    cached_type: str | None = None
    number_format: str = "General"
    xml_value: str | None = None
    xml_type: str | None = None
    xml_formula: str | None = None
    formula_attributes: tuple[tuple[str, str], ...] = ()
    merged_anchor: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location):
            raise TypeError("location must be Location")
        if set(self.location.reference) != {"sheet", "cell"}:
            raise ValueError("Cell requires sheet/cell Location")
        address(self.coordinate)
        for name in ("raw", "cached"):
            encode(getattr(self, name))
        for name in ("formula", "cached_type", "xml_value", "xml_type", "xml_formula"):
            if getattr(self, name) is not None and type(getattr(self, name)) is not str:
                raise TypeError(f"{name} must be str or None")
        for name in ("data_type", "number_format"):
            if type(getattr(self, name)) is not str:
                raise TypeError(f"{name} must be str")
        if type(self.cache_present) is not bool:
            raise TypeError("cache_present must be bool")
        attributes = tuple(tuple(pair) for pair in self.formula_attributes)
        if any(
            len(pair) != 2 or any(type(v) is not str for v in pair)
            for pair in attributes
        ):
            raise TypeError("formula_attributes must be pairs of strings")
        object.__setattr__(self, "formula_attributes", attributes)
        if self.merged_anchor is not None:
            address(self.merged_anchor)

    @property
    def coordinate(self) -> str:
        return self.location.reference["cell"]

    @property
    def value(self) -> object:
        return self.cached if self.formula is not None else self.raw

    @property
    def populated(self) -> bool:
        return self.raw is not None or self.formula is not None

    def observation(self) -> tuple[tuple[str, object], ...]:
        """A strict immutable Claim payload; Location is recorded separately."""
        return tuple(
            (f.name, getattr(self, f.name))
            for f in fields(self)
            if f.name != "location"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Worksheet:
    location: Location
    state: str
    declared_rows: int
    declared_columns: int
    cells: Mapping[str, Cell]
    merged_ranges: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or set(self.location.reference) != {
            "sheet"
        }:
            raise ValueError("Worksheet requires a sheet Location")
        validate.require_text(self.state, "state")
        if (
            type(self.declared_rows) is not int
            or not 1 <= self.declared_rows <= MAX_ROW
        ):
            raise ValueError("Invalid declared row count")
        if (
            type(self.declared_columns) is not int
            or not 1 <= self.declared_columns <= MAX_COLUMN
        ):
            raise ValueError("Invalid declared column count")
        if not isinstance(self.cells, Mapping):
            raise TypeError("cells must be a mapping")
        cells = dict(self.cells)
        for coordinate, cell in cells.items():
            address(coordinate)
            if not isinstance(cell, Cell) or cell.coordinate != coordinate:
                raise ValueError("Cell key and coordinate disagree")
            if (
                cell.location.source is not self.location.source
                or cell.location.reference["sheet"] != self.name
            ):
                raise ValueError(
                    "Cells must use the worksheet's canonical Source and name"
                )
        ranges = tuple(self.merged_ranges)
        for item in ranges:
            merged_bounds(item)
        object.__setattr__(
            self,
            "cells",
            MappingProxyType(
                dict(sorted(cells.items(), key=lambda pair: address(pair[0])))
            ),
        )
        object.__setattr__(self, "merged_ranges", ranges)

    @property
    def name(self) -> str:
        return self.location.reference["sheet"]

    def cell(self, coordinate: str) -> Cell:
        row, column = address(coordinate)
        selected = self.cells.get(coordinate)
        if selected is None:
            selected = Cell(
                location=Location(
                    source=self.location.source,
                    reference={"sheet": self.name, "cell": coordinate},
                )
            )
        for merged in self.merged_ranges:
            start, r1, c1, r2, c2 = merged_bounds(merged)
            if r1 <= row <= r2 and c1 <= column <= c2:
                return replace(selected, merged_anchor=start)
        return selected


@dataclass(frozen=True, slots=True, kw_only=True)
class WorksheetInspection:
    """Bounded worksheet preview; carries no cells or independent source identity."""

    name: str
    state: str
    declared_rows: int
    declared_columns: int
    populated_cells: int
    merged_range_count: int
    merged_ranges: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Workbook(Document):
    """A captured native workbook; Source remains its durable provenance identity."""

    source: Source
    worksheets: tuple[Worksheet, ...]
    reader_fingerprint: str
    metadata: Mapping[str, object]
    _snapshot_fingerprint: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            raise TypeError("source must be Source")
        sheets = tuple(self.worksheets)
        if any(
            not isinstance(sheet, Worksheet) or sheet.location.source is not self.source
            for sheet in sheets
        ):
            raise ValueError("Worksheets must use the workbook's canonical Source")
        if len({sheet.name for sheet in sheets}) != len(sheets):
            raise ValueError("Duplicate worksheet names")
        validate.require_text(self.reader_fingerprint, "reader_fingerprint")
        object.__setattr__(self, "worksheets", sheets)
        object.__setattr__(self, "metadata", _structured.freeze_mapping(self.metadata))
        object.__setattr__(self, "_snapshot_fingerprint", self._content_fingerprint())

    @property
    def fingerprint(self) -> str:
        return self._snapshot_fingerprint

    def _content_fingerprint(self) -> str:
        # Includes observations as well as the reader binding: manually constructed
        # snapshots cannot reuse the binding while changing inspection/extraction data.
        return _structured.fingerprint({
            "format": "rk.excel.snapshot/v1",
            "reader": self.reader_fingerprint,
            "source": (
                self.source.id,
                self.source.name,
                self.source.checksum,
                self.source.issued_at,
                self.source.received_at,
                self.source.author,
            ),
            "metadata": self.metadata,
            "sheets": tuple(
                {
                    "name": sheet.name,
                    "state": sheet.state,
                    "dimensions": (sheet.declared_rows, sheet.declared_columns),
                    "merged_ranges": sheet.merged_ranges,
                    "cells": tuple(
                        (coord, cell.observation())
                        for coord, cell in sheet.cells.items()
                    ),
                }
                for sheet in self.worksheets
            ),
        })

    @property
    def format(self) -> str:
        return "xlsx"

    @property
    def capabilities(self) -> tuple[str, ...]:
        return ("describe", "children", "inspect", "search")

    def sheet(self, name: str) -> Worksheet:
        validate.require_text(name, "sheet name")
        for sheet in self.worksheets:
            if sheet.name == name:
                return sheet
        raise KeyError(name)

    def _require_sheet(self, name: str) -> Worksheet:
        """Translate native lookup failure for both recorded inspection and extraction."""
        try:
            return self.sheet(name)
        except KeyError as exc:
            raise _Failure(
                "missing_sheet",
                "Required worksheet is not present",
                locations=(Location(source=self.source),),
                details={
                    "requested_sheet": name,
                    "available_sheets": tuple(sheet.name for sheet in self.worksheets),
                },
            ) from exc

    def _resolve(self, location: Location) -> tuple[Worksheet | None, Cell | None]:
        reference = location.reference
        if not reference:
            return None, None
        if set(reference) not in ({"sheet"}, {"sheet", "cell"}):
            raise _Failure(
                "invalid_location",
                "Expected sheet or sheet/cell reference",
                locations=(location,),
            )
        sheet = self._require_sheet(reference["sheet"])
        if "cell" not in reference:
            return sheet, None
        try:
            return sheet, sheet.cell(reference["cell"])
        except ValueError as exc:
            raise _Failure(
                "invalid_location", str(exc), locations=(sheet.location,)
            ) from exc

    def _describe(self) -> Description:
        return Description(
            source=self.source,
            format=self.format,
            capabilities=self.capabilities,
            metadata={
                "worksheet_count": len(self.worksheets),
                "populated_cells": sum(
                    sum(c.populated for c in s.cells.values()) for s in self.worksheets
                ),
            },
        )

    def _children(self, location: Location) -> Iterable[ContentItem]:
        sheet, cell = self._resolve(location)
        if sheet is None:
            for item in self.worksheets:
                yield ContentItem(
                    location=item.location, kind="worksheet", label=item.name
                )
        elif cell is None:
            for coordinate, item in sheet.cells.items():
                if item.populated:
                    yield ContentItem(
                        location=item.location, kind="cell", label=coordinate
                    )

    def _inspect(self, location: Location) -> Inspection:
        sheet, cell = self._resolve(location)
        if sheet is None:
            return Inspection(
                location=location, kind="workbook", content=self._describe()
            )
        if cell is None:
            return Inspection(
                location=location,
                kind="worksheet",
                truncated=len(sheet.merged_ranges) > 50,
                content=WorksheetInspection(
                    name=sheet.name,
                    state=sheet.state,
                    declared_rows=sheet.declared_rows,
                    declared_columns=sheet.declared_columns,
                    populated_cells=sum(
                        item.populated for item in sheet.cells.values()
                    ),
                    merged_range_count=len(sheet.merged_ranges),
                    merged_ranges=sheet.merged_ranges[:50],
                ),
            )
        updates = {name: _short(value) for name, value in cell.observation()}
        preview = replace(cell, **updates)
        return Inspection(
            location=location, kind="cell", content=preview, truncated=preview != cell
        )

    def _search(self, query: str, case_sensitive: bool) -> Iterable[ContentItem]:
        needle = query if case_sensitive else query.casefold()
        for sheet in self.worksheets:
            for cell in sheet.cells.values():
                value = cell.value
                if type(value) is str and needle in (
                    value if case_sensitive else value.casefold()
                ):
                    label = value
                    if len(label) > TEXT_PREVIEW_LIMIT:
                        label = label[: TEXT_PREVIEW_LIMIT - 1] + "…"
                    yield ContentItem(location=cell.location, kind="cell", label=label)
