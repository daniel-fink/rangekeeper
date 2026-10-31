"""The stored form of a decision trace, and the check of a stored trace (ADR-021).

The rule engine and ``check_trace`` read the records of ``run._rule.trace``. The Run
report holds ``RuleEvidence``, whose fields LinkML defines. This module converts one
to the other, so a stored Run answers to the same check as a new solve.
"""

from collections.abc import Sequence
from typing import cast

from rangekeeper.duration.dates import NEVER, DateValue
from rangekeeper.market.paths import Paths
from rangekeeper.model import Model
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.run._rule.availability import path_amounts, path_known
from rangekeeper.run._rule.result import DecisionResult
from rangekeeper.run._rule.trace import Check, Reading, TraceFacts, check_trace
from rangekeeper.schema.records import Check as CheckRecord
from rangekeeper.schema.records import (
    DecidedValue,
    Observation,
    PathCase,
    Reference,
    RuleDeclaration,
    RuleEvidence,
    TraceValue,
)
from rangekeeper.schema.runtime import UNSET, Unset
from rangekeeper.specification.rule._declaration import query_of

Traced = Quantity | DateValue


def trace_value(value: Traced) -> TraceValue:
    """Return the stored form of a Quantity, a date or NEVER."""
    if isinstance(value, Quantity):
        return TraceValue(quantity=value)
    if value is NEVER:
        return TraceValue(never=NEVER)
    return TraceValue(date=value)


def value_of(record: TraceValue) -> Traced:
    """Return the Quantity, the date or NEVER that a stored value holds."""
    if record.quantity is not None:
        return record.quantity
    if record.never is not None:
        return NEVER
    assert record.date is not None  # exactly one of the three
    return record.date


def stored_evidence(
    *, checks: Sequence[Check], provisional_solves: int, verified: bool
) -> RuleEvidence:
    """Return the stored evidence of a trace; ``decided`` comes from its records."""
    return RuleEvidence(
        checks=tuple(_check_record(check) for check in checks),
        decided=tuple(
            DecidedValue(
                target=Reference(target=check.rule),
                key=check.key,
                value=trace_value(cast(Traced, check.value)),
                decision_date=check.on,
            )
            for check in checks
            if check.result in (DecisionResult.DECIDED, DecisionResult.OTHERWISE)
        ),
        provisional_solves=provisional_solves,
        verified=verified,
    )


def read_checks(evidence: RuleEvidence) -> tuple[Check, ...]:
    """Return the records of a stored trace, in order."""
    return tuple(_check(record) for record in evidence.checks)


def check_stored(
    evidence: RuleEvidence,
    *,
    rules: Sequence[RuleDeclaration],
    candidate: Model,
    path: PathCase | None,
    paths: Paths | None,
    units: UnitSystem,
) -> None:
    """Raise DecisionError with ``rule_trace`` when a stored trace does not hold."""
    known, amounts = {}, {}
    if path is not None and paths is not None:
        known = dict(path_known(path=path, paths=paths))
        amounts = dict(path_amounts(path=path, paths=paths))
    check_trace(
        rules=tuple(query_of(rule) for rule in rules),
        checks=read_checks(evidence),
        facts=TraceFacts(
            candidate=candidate,
            path_known=known,
            path_amounts=amounts,
            # A Specification holds no rule parameters yet (#301).
            parameters={},
            units=units,
        ),
    )


def _check_record(check: Check) -> CheckRecord:
    return CheckRecord(
        target=Reference(target=check.rule),
        key=check.key,
        date=check.on,
        result=check.result,
        condition=UNSET if check.condition is None else check.condition,
        observations=(
            tuple(_observation(item) for item in check.readings)
            if check.readings
            else UNSET
        ),
        earliest=_optional(check.earliest),
        latest=_optional(check.latest),
        value=_optional(check.value),
    )


def _observation(reading: Reading) -> Observation:
    return Observation(
        name=reading.name,
        target=Reference(target=reading.target),
        source=reading.source,
        value=_optional(reading.value),
        available_on=UNSET if reading.available_on is None else reading.available_on,
    )


def _optional(value: Traced | None) -> TraceValue | Unset:
    return UNSET if value is None else trace_value(value)


def _check(record: CheckRecord) -> Check:
    return Check(
        rule=record.target.target,
        key=record.key,
        on=record.date,
        result=record.result,
        readings=tuple(_reading(item) for item in record.observations or ()),
        condition=record.condition,
        earliest=cast(DateValue | None, _held(record.earliest)),
        latest=cast(DateValue | None, _held(record.latest)),
        value=_held(record.value),
    )


def _reading(record: Observation) -> Reading:
    return Reading(
        name=record.name,
        target=record.target.target,
        value=_held(record.value),
        available_on=record.available_on,
        source=record.source,
    )


def _held(record: TraceValue | None) -> Traced | None:
    return None if record is None else value_of(record)


__all__ = [
    "check_stored",
    "read_checks",
    "stored_evidence",
    "trace_value",
    "value_of",
]
