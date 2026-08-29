from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, TypeVar
from uuid import UUID, uuid4

import pint

from .. import validate
from ..measure import Measure
from .classification import Classification


T = TypeVar("T")


@dataclass(frozen=True, slots=True, kw_only=True)
class Label:
    id: UUID = field(default_factory=uuid4)
    key: str
    classifications: tuple[Classification, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not validate.is_text(self.key):
            raise TypeError("Label.key must be a string")
        if not validate.is_text(self.key, empty=False):
            raise ValueError("Label.key must not be empty")
        classifications = tuple(self.classifications)
        if any(not isinstance(item, Classification) for item in classifications):
            raise TypeError("classifications must contain only Classification objects")
        ids = tuple(item.id for item in classifications)
        if len(ids) != len(set(ids)):
            raise ValueError("a label cannot repeat a classification")
        object.__setattr__(self, "classifications", classifications)


@dataclass(frozen=True, slots=True, kw_only=True)
class Measurement:
    id: UUID = field(default_factory=uuid4)
    measure: Measure
    quantity: pint.Quantity

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not isinstance(self.measure, Measure):
            raise TypeError("measure must be a Measure")
        self.measure.validate_quantity(self.quantity)


@dataclass(frozen=True, slots=True, kw_only=True)
class Feature(Generic[T]):
    """A named value with shallow immutability and reference semantics."""

    id: UUID = field(default_factory=uuid4)
    name: str
    value: T | None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not validate.is_text(self.name):
            raise TypeError("Feature.name must be a string")
        if not validate.is_text(self.name, empty=False):
            raise ValueError("Feature.name must not be empty")


@dataclass(frozen=True, slots=True)
class Characteristics:
    labels: Mapping[str, Label] = field(default_factory=dict)
    measurements: Mapping[str, Measurement] = field(default_factory=dict)
    features: Mapping[str, Feature] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, name in (
            (self.labels, "labels"),
            (self.measurements, "measurements"),
            (self.features, "features"),
        ):
            if not isinstance(value, Mapping):
                raise TypeError(f"{name} must be a mapping")

        labels = dict(self.labels)
        measurements = dict(self.measurements)
        features = dict(self.features)

        if any(not isinstance(item, Label) for item in labels.values()):
            raise TypeError("labels must contain only Label objects")
        if any(key != item.key for key, item in labels.items()):
            raise ValueError("label mapping keys must match Label.key")
        if any(not isinstance(item, Measurement) for item in measurements.values()):
            raise TypeError("measurements must contain only Measurement objects")
        if any(code != item.measure.code for code, item in measurements.items()):
            raise ValueError("measurement mapping keys must match Measure.code")
        if any(not isinstance(item, Feature) for item in features.values()):
            raise TypeError("features must contain only Feature objects")
        if any(name != item.name for name, item in features.items()):
            raise ValueError("feature mapping keys must match Feature.name")

        object.__setattr__(self, "labels", MappingProxyType(labels))
        object.__setattr__(self, "measurements", MappingProxyType(measurements))
        object.__setattr__(self, "features", MappingProxyType(features))

    def label(self, key: str) -> Label | None:
        if not isinstance(key, str):
            raise TypeError("key must be a string")
        return self.labels.get(key)

    def measurement(self, measure: Measure | str) -> Measurement | None:
        measure_code = measure.code if isinstance(measure, Measure) else measure
        if not isinstance(measure_code, str):
            raise TypeError("measure must be a Measure or code")
        return self.measurements.get(measure_code)

    def feature(self, name: str) -> Feature | None:
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        return self.features.get(name)

    @property
    def items(self) -> tuple[Label | Measurement | Feature, ...]:
        return (
            *self.labels.values(),
            *self.measurements.values(),
            *self.features.values(),
        )
