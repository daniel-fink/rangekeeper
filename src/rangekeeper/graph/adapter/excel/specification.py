"""Strict, ordered physical-range extraction requests; no project interpretation."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .... import validate
from .._structured import freeze
from ..errors import AdapterEncodingError
from ._coordinates import MAX_ROW, address, column_number


def _comparison(value: str) -> None:
    if value not in ("exact", "trim"):
        raise ValueError("comparison must be exact or trim")


def _value(value: object) -> None:
    normalized = freeze(value)
    if isinstance(normalized, Mapping) or type(normalized) in (tuple, frozenset):
        raise ValueError("Expected a scalar comparison value")


def _fields(
    value: object,
    allowed: set[str],
    required: set[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Expected a specification mapping")
    if any(type(key) is not str for key in value):
        raise ValueError("Specification keys must be strings")
    if set(value) - allowed:
        raise ValueError(f"Unknown fields: {sorted(set(value) - allowed)}")
    if required - set(value):
        raise ValueError(f"Missing fields: {sorted(required - set(value))}")
    return dict(value)


@dataclass(frozen=True, slots=True, kw_only=True)
class Column:
    """Map one source column to a named output column; not stored Table data."""

    name: str
    column: str

    def __post_init__(self) -> None:
        validate.require_text(self.name, "column name")
        column_number(self.column)


@dataclass(frozen=True, slots=True, kw_only=True)
class Expectations:
    """Layout guards evaluated before any output Claims are constructed."""

    cells: Mapping[str, object] = field(default_factory=dict)
    comparison: str = "exact"

    def __post_init__(self) -> None:
        _comparison(self.comparison)
        if not isinstance(self.cells, Mapping):
            raise TypeError("expect.cells must be a mapping")
        cells = dict(self.cells)
        for coordinate, expected in cells.items():
            address(coordinate)
            _value(expected)
        object.__setattr__(self, "cells", MappingProxyType(cells))


@dataclass(frozen=True, slots=True, kw_only=True)
class StopBefore:
    """Exclusive physical stopping marker, not a semantic row filter."""

    column: str
    equals: object
    comparison: str = "exact"

    def __post_init__(self) -> None:
        column_number(self.column)
        _comparison(self.comparison)
        _value(self.equals)


@dataclass(frozen=True, slots=True, kw_only=True)
class Rows:
    """Physical extraction bounds; distinct from graph.table.Row values."""

    start: int
    end: int | None = None
    stop_before: StopBefore | None = None

    def __post_init__(self) -> None:
        if type(self.start) is not int or not 1 <= self.start <= MAX_ROW:
            raise ValueError("rows.start must be an Excel row number")
        if (self.end is None) == (self.stop_before is None):
            raise ValueError("Specify exactly one of rows.end or rows.stop_before")
        if self.end is not None and (
            type(self.end) is not int or not self.start <= self.end <= MAX_ROW
        ):
            raise ValueError("rows.end must be an inclusive row at or after start")
        if self.stop_before is not None and not isinstance(
            self.stop_before, StopBefore
        ):
            raise TypeError("stop_before must be StopBefore")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractionSpec:
    """Complete versioned request for one physical worksheet extraction."""

    id: str
    version: int
    sheet: str
    rows: Rows
    columns: tuple[Column, ...]
    expect: Expectations = field(default_factory=Expectations)
    formula_values: str = "cached"

    def __post_init__(self) -> None:
        validate.require_text(self.id, "id")
        validate.require_text(self.sheet, "sheet")
        if type(self.version) is not int or self.version != 1:
            raise ValueError("Only extraction schema version 1 is supported")
        if not isinstance(self.rows, Rows) or not isinstance(self.expect, Expectations):
            raise TypeError("rows and expect must be their typed specifications")
        columns = tuple(self.columns)
        if not columns or any(not isinstance(item, Column) for item in columns):
            raise ValueError("columns must be a nonempty ordered sequence of Column")
        if len({item.name for item in columns}) != len(columns):
            raise ValueError("Output column names must be unique")
        if self.formula_values != "cached":
            raise ValueError("Only cached formula values are supported")
        object.__setattr__(self, "columns", columns)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ExtractionSpec":
        # Reject cyclic/mutable unsupported inputs before walking the schema.
        normalized = freeze(value)
        fields = _fields(
            normalized,
            {"id", "version", "sheet", "rows", "columns", "expect", "formula_values"},
            {"id", "version", "sheet", "rows", "columns"},
        )
        rows = _fields(fields["rows"], {"start", "end", "stop_before"}, {"start"})
        if "stop_before" in rows:
            rows["stop_before"] = StopBefore(
                **_fields(
                    rows["stop_before"],
                    {"column", "equals", "comparison"},
                    {"column", "equals"},
                )
            )
        fields["rows"] = Rows(**rows)
        if type(fields["columns"]) is not tuple:
            raise TypeError("columns must be an ordered sequence")
        fields["columns"] = tuple(
            Column(**_fields(item, {"name", "column"}, {"name", "column"}))
            for item in fields["columns"]
        )
        if "expect" in fields:
            fields["expect"] = Expectations(
                **_fields(
                    fields["expect"],
                    {"comparison", "cells"},
                    {"cells"},
                )
            )
        return cls(**fields)

    def to_mapping(self) -> Mapping[str, object]:
        rows: dict[str, object] = {"start": self.rows.start}
        if self.rows.stop_before is not None:
            stop = self.rows.stop_before
            rows["stop_before"] = {
                "column": stop.column,
                "equals": stop.equals,
                "comparison": stop.comparison,
            }
        else:
            rows["end"] = self.rows.end
        return {
            "id": self.id,
            "version": self.version,
            "sheet": self.sheet,
            "rows": rows,
            "columns": tuple(
                {"name": c.name, "column": c.column} for c in self.columns
            ),
            "expect": {
                "cells": self.expect.cells,
                "comparison": self.expect.comparison,
            },
            "formula_values": self.formula_values,
        }


def load_specification(content: str) -> ExtractionSpec:
    """Decode YAML text; no includes, executable tags, duplicate keys or silent coercion."""
    if type(content) is not str:
        raise TypeError("YAML content must be str")
    try:
        import yaml
        from yaml.resolver import BaseResolver
    except ImportError as exc:
        raise ImportError("YAML specifications require Rangekeeper[excel]") from exc

    class UniqueLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if type(key) is not str:
                raise AdapterEncodingError("YAML mapping keys must be strings")
            if key in result:
                raise AdapterEncodingError(f"Duplicate YAML key: {key}")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    UniqueLoader.add_constructor(
        BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping,
    )
    try:
        supplied = yaml.load(content, Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        raise AdapterEncodingError(f"Invalid extraction YAML: {exc}") from exc
    return ExtractionSpec.from_mapping(supplied)
