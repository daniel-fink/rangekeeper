from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import pint

from ..measure import Measure
from .classification import Classification


@dataclass
class Characteristics:
    occupancy: dict[str, tuple[Classification, ...]] = field(default_factory=dict)
    measures: dict[Measure, pint.Quantity] = field(default_factory=dict)
    features: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        initial_occupancy = dict(self.occupancy)
        initial_measures = dict(self.measures)
        self.occupancy = {}
        self.measures = {}
        self.features = dict(self.features)
        for facet, classifications in initial_occupancy.items():
            self.set_occupancy(facet, classifications)
        for measure, quantity in initial_measures.items():
            self.set_measure(measure, quantity)

    def set_occupancy(
        self,
        facet: str,
        classifications: Iterable[Classification],
    ) -> None:
        if not isinstance(facet, str):
            raise TypeError("occupancy facet must be a string")
        if not facet.strip():
            raise ValueError("occupancy facet must not be empty")
        if isinstance(classifications, (Classification, str, bytes)):
            raise TypeError("occupancy values must be an iterable of Classifications")
        try:
            values = tuple(classifications)
        except TypeError as error:
            raise TypeError(
                "occupancy values must be an iterable of Classifications"
            ) from error
        if not all(isinstance(value, Classification) for value in values):
            raise TypeError("occupancy values must contain only Classifications")
        keys = [value.key for value in values]
        if len(keys) != len(set(keys)):
            raise ValueError("occupancy values must not repeat a classification key")
        self.occupancy[facet] = values

    def remove_occupancy(self, facet: str) -> tuple[Classification, ...]:
        return self.occupancy.pop(facet)

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
