"""Immutable runtime observations and rule evidence, with derived assignments."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum, unique

from rangekeeper.schema.records import Assignment, ObservedQuantity, RuleEvidence


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
class RuleResult:
    """Ordered evidence makes no claim about numerical feasibility."""

    evidence: tuple[RuleEvidence, ...]

    def __post_init__(self):
        items = tuple(self.evidence)
        if any(not isinstance(item, RuleEvidence) for item in items):
            raise TypeError("evidence must be RuleEvidence records")
        object.__setattr__(self, "evidence", items)

    @property
    def assignments(self) -> tuple[Assignment, ...]:
        """Return the assignments of all evidence, in order."""
        return tuple(item for outcome in self.evidence for item in outcome.assignments)


@unique
class DecisionResult(StrEnum):
    """The result of one check of a decision rule (ADR-021).

    Each member's value is the text that rule evidence records.
    """

    DECIDED = "decided"
    """The condition held, so the rule decided the value on this date."""
    NOT_MET = "not_met"
    """The condition did not hold on this date; the rule keeps checking."""
    SKIPPED = "skipped"
    """The rule did not test its condition on this date."""
    OTHERWISE = "otherwise"
    """No check decided the value, so the ``otherwise`` value applies."""

    @classmethod
    def of(cls, evidence: RuleEvidence) -> "DecisionResult":
        """Return the result of one recorded decision.

        A decision with a matched ``rule`` is ``DECIDED``; a decision without
        one took its fallback, so it is ``OTHERWISE``.
        """
        if not isinstance(evidence, RuleEvidence):
            raise TypeError("evidence must be a RuleEvidence record")
        return cls.DECIDED if evidence.rule is not None else cls.OTHERWISE
