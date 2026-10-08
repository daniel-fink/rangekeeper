"""Immutable runtime observations and policy outcomes, with derived assignments."""

from dataclasses import dataclass
from datetime import date

from rangekeeper.schema.records import Assignment, DecisionOutcome, ObservedQuantity


@dataclass(frozen=True, slots=True)
class Observation:
    """Only quantities available at one date; no Model or resolver handle."""

    at: date
    quantities: tuple[ObservedQuantity, ...]

    def __post_init__(self):
        if type(self.at) is not date:
            raise TypeError("observation at must be a date")
        items = tuple(self.quantities)
        if any(not isinstance(item, ObservedQuantity) for item in items):
            raise TypeError("observation quantities must be ObservedQuantity records")
        object.__setattr__(self, "quantities", items)


@dataclass(frozen=True, slots=True)
class PolicyResult:
    """Ordered outcomes make no claim about numerical feasibility."""

    outcomes: tuple[DecisionOutcome, ...]

    def __post_init__(self):
        items = tuple(self.outcomes)
        if any(not isinstance(item, DecisionOutcome) for item in items):
            raise TypeError("outcomes must be DecisionOutcome records")
        object.__setattr__(self, "outcomes", items)

    @property
    def assignments(self) -> tuple[Assignment, ...]:
        return tuple(item for outcome in self.outcomes for item in outcome.assignments)
