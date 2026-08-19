from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class Record:
    record_type: str
    identifier: str
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        for value, field in (
            (self.record_type, "record_type"),
            (self.identifier, "identifier"),
        ):
            if not isinstance(value, str):
                raise TypeError(f"{field} must be a string")
            if not value.strip():
                raise ValueError(f"{field} must not be empty")
        if not isinstance(self.values, Mapping):
            raise TypeError("values must be a mapping")
        object.__setattr__(self, "values", _freeze(dict(self.values)))


@dataclass(frozen=True)
class Snapshot:
    schema_version: int
    records: tuple[Record, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, int):
            raise TypeError("schema_version must be an integer")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        records = tuple(self.records)
        if not all(isinstance(record, Record) for record in records):
            raise TypeError("records must contain only Record instances")
        keys = [(record.record_type, record.identifier) for record in records]
        if len(keys) != len(set(keys)):
            raise ValueError("Snapshot record type/identifier pairs must be unique")
        object.__setattr__(self, "records", records)
