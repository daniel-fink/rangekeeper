from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from .characteristics import Characteristics, Feature, Label, Measurement
from .classification import Classification


@dataclass(frozen=True, slots=True, kw_only=True)
class Entity:
    """An immutable domain object with UUID identity."""

    id: UUID = field(default_factory=uuid4)
    code: str | None = None
    name: str | None = None
    classification: Classification | None = None
    characteristics: Characteristics = field(default_factory=Characteristics)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        for value, field_name in ((self.code, "code"), (self.name, "name")):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{field_name} must be a string or None")
        if self.classification is not None and not isinstance(
            self.classification, Classification
        ):
            raise TypeError("classification must be a Classification or None")
        if not isinstance(self.characteristics, Characteristics):
            raise TypeError("characteristics must be Characteristics")

    @property
    def labels(self) -> Mapping[str, Label]:
        return self.characteristics.labels

    @property
    def measurements(self) -> Mapping[str, Measurement]:
        return self.characteristics.measurements

    @property
    def features(self) -> Mapping[str, Feature]:
        return self.characteristics.features
