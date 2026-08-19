from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .errors import SnapshotError


@dataclass(frozen=True)
class Fields:
    values: Mapping[str, object]
    owner: str

    def __post_init__(self) -> None:
        if not isinstance(self.values, Mapping):
            raise SnapshotError(f"{self.owner} must be a mapping")

    def get(self, name: str) -> object:
        return self.values.get(name)

    def required(self, name: str) -> object:
        try:
            return self.values[name]
        except KeyError as error:
            raise SnapshotError(f"{self.owner} is missing {name!r}") from error

    def text(self, name: str) -> str:
        value = self.required(name)
        if not isinstance(value, str):
            raise SnapshotError(f"{self.owner} field {name!r} must be a string")
        return value

    def mapping(self, name: str) -> Mapping[str, object]:
        value = self.required(name)
        if not isinstance(value, Mapping):
            raise SnapshotError(f"{self.owner} field {name!r} must be a mapping")
        return value

    def sequence(self, name: str) -> tuple[object, ...]:
        value = self.required(name)
        if not isinstance(value, (list, tuple)):
            raise SnapshotError(f"{self.owner} field {name!r} must be a sequence")
        return tuple(value)

    def texts(self, name: str, *, unique: bool = False) -> tuple[str, ...]:
        values = self.sequence(name)
        if not all(isinstance(value, str) for value in values):
            raise SnapshotError(f"{self.owner} field {name!r} must contain strings")
        if unique and len(values) != len(set(values)):
            raise SnapshotError(f"{self.owner} field {name!r} contains duplicates")
        return values

    def mappings(self, name: str) -> tuple[Mapping[str, object], ...]:
        values = self.sequence(name)
        if not all(isinstance(value, Mapping) for value in values):
            raise SnapshotError(f"{self.owner} field {name!r} must contain mappings")
        return values
