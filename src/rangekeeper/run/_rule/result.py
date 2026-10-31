"""The result of one check of a rule, which the rule engine and the trace check read."""

from enum import StrEnum, unique

from rangekeeper.schema.records import RuleEvidence


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
