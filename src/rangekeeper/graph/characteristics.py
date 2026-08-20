from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import pint

from ..measure import Measure
from .classification import Classification


@dataclass
class Characteristics:
    labels: dict[str, tuple[Classification, ...]] = field(default_factory=dict)
    measures: dict[Measure, pint.Quantity] = field(default_factory=dict)
    features: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        initial_labels = dict(self.labels)
        initial_measures = dict(self.measures)
        self.labels = {}
        self.measures = {}
        self.features = dict(self.features)
        for key, classifications in initial_labels.items():
            self.set_labels(key, classifications)
        for measure, quantity in initial_measures.items():
            self.set_measure(measure, quantity)

    def set_labels(
        self,
        key: str,
        classifications: Iterable[Classification],
    ) -> None:
        if not isinstance(key, str):
            raise TypeError("label key must be a string")
        if not key.strip():
            raise ValueError("label key must not be empty")
        if isinstance(classifications, (Classification, str, bytes)):
            raise TypeError("label values must be an iterable of Classifications")
        try:
            values = tuple(classifications)
        except TypeError as error:
            raise TypeError(
                "label values must be an iterable of Classifications"
            ) from error
        if not all(isinstance(value, Classification) for value in values):
            raise TypeError("label values must contain only Classifications")
        classification_keys = [value.key for value in values]
        if len(classification_keys) != len(set(classification_keys)):
            raise ValueError("label values must not repeat a classification key")
        self.labels[key] = values

    def remove_labels(self, key: str) -> tuple[Classification, ...]:
        return self.labels.pop(key)

    def get_measure(self, measure: Measure) -> pint.Quantity | None:
        stored_measure = self._resolve_measure(measure)
        if stored_measure is None:
            return None
        return self.measures[stored_measure]

    def require_measure(self, measure: Measure) -> pint.Quantity:
        quantity = self.get_measure(measure)
        if quantity is None:
            raise KeyError(f"measure {measure.code!r} is not available")
        return quantity

    def set_measure(self, measure: Measure, quantity: pint.Quantity) -> None:
        if not isinstance(measure, Measure):
            raise TypeError("measure must be a Measure")
        measure.validate_quantity(quantity)

        stored_measure = self._resolve_measure(measure)
        key = measure if stored_measure is None else stored_measure
        self.measures[key] = quantity

    def remove_measure(self, measure: Measure) -> pint.Quantity:
        stored_measure = self._resolve_measure(measure)
        if stored_measure is None:
            raise KeyError(f"measure {measure.code!r} is not available")
        return self.measures.pop(stored_measure)

    def _resolve_measure(self, measure: Measure) -> Measure | None:
        if not isinstance(measure, Measure):
            raise TypeError("measure must be a Measure")
        for stored_measure in self.measures:
            if stored_measure == measure:
                stored_measure.assert_consistent_with(measure)
                return stored_measure
        return None
