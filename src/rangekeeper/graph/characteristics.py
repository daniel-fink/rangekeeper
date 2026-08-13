from __future__ import annotations

from dataclasses import dataclass, field

import pint

from ..measure import Measure


@dataclass
class Characteristics:
    use: object | None = None
    tenure: object | None = None
    measures: dict[Measure, pint.Quantity] = field(default_factory=dict)
    features: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        initial_measures = dict(self.measures)
        self.measures = {}
        self.features = dict(self.features)
        for measure, quantity in initial_measures.items():
            self.set_measure(measure, quantity)

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
