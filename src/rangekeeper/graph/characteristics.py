from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Generic, TypeVar
from uuid import UUID, uuid4

import pint

from .. import validate
from ..measure import Measure
from .classification import Classification


T = TypeVar("T")

__all__ = ["Characteristics", "Feature", "Label", "Measurement"]


def _freeze_items(
    values: Mapping[str, T],
    *,
    item_type: type[T],
    key_of: Callable[[T], str],
    field_name: str,
) -> Mapping[str, T]:
    """Copy and freeze keyed items so caller mappings cannot mutate owners."""

    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    copied = dict(values)
    if any(not isinstance(item, item_type) for item in copied.values()):
        raise TypeError(f"{field_name} must contain only {item_type.__name__} objects")
    if any(key != key_of(item) for key, item in copied.items()):
        raise ValueError(f"{field_name} mapping keys do not match item keys")
    return MappingProxyType(copied)


@dataclass(frozen=True, slots=True, kw_only=True)
class Label:
    """A keyed set of classifications attached to a graph object."""

    id: UUID = field(default_factory=uuid4)
    key: str
    classifications: tuple[Classification, ...]

    def __post_init__(self) -> None:
        validate.require_uuid(self.id, "id")
        validate.require_text(self.key, "Label.key")
        classifications = tuple(self.classifications)
        if any(not isinstance(item, Classification) for item in classifications):
            raise TypeError("classifications must contain only Classification objects")
        ids = tuple(item.id for item in classifications)
        if len(ids) != len(set(ids)):
            raise ValueError("a label cannot repeat a classification")
        object.__setattr__(self, "classifications", classifications)


@dataclass(frozen=True, slots=True, kw_only=True)
class Measurement:
    """A quantity interpreted through its canonical Measure definition."""

    id: UUID = field(default_factory=uuid4)
    measure: Measure
    quantity: pint.Quantity

    def __post_init__(self) -> None:
        validate.require_uuid(self.id, "id")
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
        validate.require_uuid(self.id, "id")
        validate.require_text(self.name, "Feature.name")


@dataclass(frozen=True, slots=True)
class Characteristics:
    """Immutable keyed characteristics shared by entities and relationships."""

    labels: Mapping[str, Label] = field(default_factory=dict)
    measurements: Mapping[str, Measurement] = field(default_factory=dict)
    features: Mapping[str, Feature] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "labels",
            _freeze_items(
                self.labels,
                item_type=Label,
                key_of=lambda item: item.key,
                field_name="labels",
            ),
        )
        object.__setattr__(
            self,
            "measurements",
            _freeze_items(
                self.measurements,
                item_type=Measurement,
                key_of=lambda item: item.measure.code,
                field_name="measurements",
            ),
        )
        object.__setattr__(
            self,
            "features",
            _freeze_items(
                self.features,
                item_type=Feature,
                key_of=lambda item: item.name,
                field_name="features",
            ),
        )

    def label(self, key: str) -> Label | None:
        """Return the label with this key, if present."""

        if not isinstance(key, str):
            raise TypeError("key must be a string")
        return self.labels.get(key)

    def measurement(self, measure: Measure | str) -> Measurement | None:
        """Return the measurement for a Measure or measure code."""

        measure_code = measure.code if isinstance(measure, Measure) else measure
        if not isinstance(measure_code, str):
            raise TypeError("measure must be a Measure or code")
        return self.measurements.get(measure_code)

    def feature(self, name: str) -> Feature | None:
        """Return the feature with this name, if present."""

        if not isinstance(name, str):
            raise TypeError("name must be a string")
        return self.features.get(name)

    @property
    def items(self) -> tuple[Label | Measurement | Feature, ...]:
        """Return all characteristics in stable label, measurement, feature order."""

        return (
            *self.labels.values(),
            *self.measurements.values(),
            *self.features.values(),
        )
