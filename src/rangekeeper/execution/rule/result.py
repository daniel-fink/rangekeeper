"""Immutable runtime observations and rule evidence, with derived assignments."""

from dataclasses import dataclass
from datetime import date

from rangekeeper.run._rule.result import DecisionResult as DecisionResult
from rangekeeper.schema.records import Assignment, ObservedQuantity, RuleEvidence


@dataclass(frozen=True, kw_only=True, slots=True)
class Observation:
    """Only quantities available at one date; no Model or resolver handle."""

    at: date
    quantities: tuple[ObservedQuantity, ...]

    def __post_init__(self) -> None:
        if type(self.at) is not date:
            raise TypeError("observation at must be a date")
        items = tuple(self.quantities)
        if any(not isinstance(item, ObservedQuantity) for item in items):
            raise TypeError("observation quantities must be ObservedQuantity records")
        object.__setattr__(self, "quantities", items)


@dataclass(frozen=True, kw_only=True, slots=True)
class RuleResult:
    """Ordered evidence makes no claim about numerical feasibility."""

    evidence: tuple[RuleEvidence, ...]

    def __post_init__(self) -> None:
        items = tuple(self.evidence)
        if any(not isinstance(item, RuleEvidence) for item in items):
            raise TypeError("evidence must be RuleEvidence records")
        object.__setattr__(self, "evidence", items)

    @property
    def assignments(self) -> tuple[Assignment, ...]:
        """Return the assignments of all evidence, in order."""
        return tuple(item for outcome in self.evidence for item in outcome.assignments)
