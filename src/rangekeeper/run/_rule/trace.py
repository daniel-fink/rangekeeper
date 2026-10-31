"""The decision trace of one case, and its check (ADR-021).

The rule engine in ``execution.rule`` records a ``Check`` for each window date.
``check_trace`` does not trust that record. It reads only the declarations, the
recorded readings, the path data and the serialized candidate, so it can run on a
stored Run without a solve. #300 defines the stored fields of these records in
LinkML.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum, unique
from math import isclose
from uuid import UUID

from rangekeeper.duration.dates import NEVER, DateValue
from rangekeeper.flow import Movement
from rangekeeper.model import Model
from rangekeeper.model.expression.evaluation import compare_dates, evaluate_date
from rangekeeper.model.expression.text import render
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.run._rule.availability import known_on
from rangekeeper.run._rule.result import DecisionResult
from rangekeeper.run._rule.truth import UNKNOWN, truth
from rangekeeper.schema.enums import ValueKind
from rangekeeper.schema.records import (
    Expression,
    ExpressionKind,
    Operator,
    Reference,
    Value,
)
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, DecisionError
from rangekeeper.specification.rule._query import (
    RuleQuery,
    leaves,
    parameter_id,
    read_targets,
)


@unique
class Source(StrEnum):
    """Where the value of a reading comes from."""

    PATH = "path"
    FIXED = "fixed"
    PARAMETER = "parameter"
    DECIDED = "decided"
    SOLVED = "solved"


@dataclass(frozen=True, kw_only=True)
class Reading:
    """One value that a rule read on a window date.

    ``value`` None means that the value is undecided, so the reading is unknown.
    ``available_on`` None means that the value is always available: a fixed value
    or a parameter. ``target`` is the Movement, for a reading of a Flow.
    """

    name: str
    target: UUID
    value: Quantity | DateValue | None
    available_on: date | None
    source: Source


@dataclass(frozen=True, kw_only=True)
class Check:
    """One record of the trace: a window date of a rule, or its ``otherwise``.

    ``condition`` is True, False or None for unknown; a record without a test has
    None too. ``earliest`` and ``latest`` are the bounds of the rule on that date:
    None for an undecided bound or a rule without one. ``value`` is the value that
    the record fixes, when it fixes one.
    """

    rule: UUID
    key: str
    on: date
    result: DecisionResult
    readings: tuple[Reading, ...] = ()
    condition: bool | None = None
    earliest: DateValue | None = None
    latest: DateValue | None = None
    value: Quantity | DateValue | None = None


def leaf_name(leaf: Expression, *, name: Callable[[Reference], str]) -> str:
    """Return the name of a reading: the text of what the condition reads."""
    return render(expression=leaf, name=name)


def naming(*, model: Model, parameters: Iterable[str]) -> Callable[[Reference], str]:
    """Return the function that names a reference: a parameter's key, or a Value's."""
    keys = {parameter_id(key): key for key in parameters}

    def name(reference: Reference) -> str:
        found = keys.get(reference.target)
        return found if found is not None else model.key_of(reference.target)

    return name


def calendar(
    rule: RuleQuery, *, model: Model, path_known: Mapping[UUID, date]
) -> tuple[date, ...]:
    """Return the dates of a rule's calendar, in order, without its bounds.

    With ``periods``, the ``timing`` day of each Period. Otherwise each date on
    which an amount of a Flow that the condition reads becomes known; a condition
    that reads no Flow has no calendar of its own.
    """
    if rule.periods is not None:
        return tuple(sorted({p.resolve(timing=rule.timing) for p in rule.periods}))
    found: set[date] = set()
    for target in read_targets(rule.condition):
        flow = _flow_of(model, target)
        if flow is not None:
            found.update(path_known.get(m.id, known_on(m)) for m in flow)
    return tuple(sorted(found))


def _flow_of(model: Model, target: UUID) -> tuple[Movement, ...] | None:
    record = model._index.records.get(target)
    if isinstance(record, Value) and record.kind is ValueKind.FLOW:
        assert record.flow is not None
        return tuple(record.flow.movements)
    return None


@dataclass(frozen=True, kw_only=True)
class _Trace:
    """What the check of one trace reads."""

    rules: tuple[RuleQuery, ...]
    candidate: Model
    path_known: Mapping[UUID, date]
    path_amounts: Mapping[UUID, Quantity]
    parameters: Mapping[str, Quantity]
    units: UnitSystem
    absolute: float
    relative: float
    finals: Mapping[UUID, Check]
    values: Mapping[UUID, Quantity | DateValue]


@dataclass(frozen=True, kw_only=True)
class TraceFacts:
    """The facts that a trace answers to: the case's path data and its candidate."""

    candidate: Model
    path_known: Mapping[UUID, date]
    path_amounts: Mapping[UUID, Quantity]
    parameters: Mapping[str, Quantity]
    units: UnitSystem
    absolute: float = 1e-8
    relative: float = 1e-9


def check_trace(
    *,
    rules: Sequence[RuleQuery],
    checks: Sequence[Check],
    facts: TraceFacts,
) -> None:
    """Raise DecisionError with ``rule_trace`` when a trace does not hold.

    It checks the order of the records and the windows and their bounds; each
    reading's availability and value against the path data and the candidate;
    each condition against its readings; that each value is fixed on the first
    window date where the condition holds, or ``otherwise`` on a date that the
    window allows; and that the candidate holds each decided value.
    """
    finals = _check_order(tuple(rules), checks)
    trace = _Trace(
        rules=tuple(rules),
        candidate=facts.candidate,
        path_known=facts.path_known,
        path_amounts=facts.path_amounts,
        parameters=facts.parameters,
        units=facts.units,
        absolute=facts.absolute,
        relative=facts.relative,
        finals=finals,
        values={
            **candidate_values(facts.candidate),
            **{parameter_id(key): item for key, item in facts.parameters.items()},
        },
    )
    by_target = {rule.target: rule for rule in rules}
    decided: set[UUID] = set()
    for check in checks:
        rule = by_target[check.rule]
        _check_bounds(check, rule=rule, trace=trace)
        for reading in check.readings:
            _check_reading(reading, check=check, trace=trace, decided=decided)
        _check_result(check, rule=rule, trace=trace)
        if check.result in (DecisionResult.DECIDED, DecisionResult.OTHERWISE):
            decided.add(check.rule)
    for rule in rules:
        _check_final(rule, checks=checks, trace=trace)


def _fail(message: str, *, check: Check | None = None) -> DecisionError:
    values = (
        {}
        if check is None
        else {"key": check.key, "on": check.on.isoformat(), "result": check.result}
    )
    return DecisionError(
        f"decision trace: {message}", code=Code.RULE_TRACE, values=values
    )


def _check_order(
    rules: tuple[RuleQuery, ...], checks: Sequence[Check]
) -> Mapping[UUID, Check]:
    """Check the written order and date order; return each rule's final record."""
    position = {rule.target: index for index, rule in enumerate(rules)}
    finals: dict[UUID, Check] = {}
    previous: Check | None = None
    for check in checks:
        if check.rule not in position:
            raise _fail("a record of no rule", check=check)
        if check.rule in finals:
            raise _fail("a record after the rule fixed its value", check=check)
        if previous is not None and check.on < previous.on:
            raise _fail("records out of date order", check=check)
        if (
            previous is not None
            and check.on == previous.on
            and check.result is not DecisionResult.OTHERWISE
            and position[check.rule] <= position[previous.rule]
        ):
            raise _fail("records out of the written order", check=check)
        if check.result in (DecisionResult.DECIDED, DecisionResult.OTHERWISE):
            finals[check.rule] = check
        previous = check
    missing = [rule for rule in rules if rule.target not in finals]
    if missing:
        raise _fail("a rule that fixes no value")
    return finals


def _bound(node: Expression | None, *, trace: _Trace) -> DateValue | None:
    """Return a bound from the candidate's final dates; None without a bound."""
    if node is None:
        return None
    try:
        return evaluate_date(node, trace.values, units=trace.units)
    except (KeyError, ContractError) as error:
        raise _fail(f"a bound that the candidate does not give: {error}") from error


def _check_bounds(check: Check, *, rule: RuleQuery, trace: _Trace) -> None:
    for recorded, node in (
        (check.earliest, rule.earliest),
        (check.latest, rule.latest),
    ):
        if recorded is not None and recorded != _bound(node, trace=trace):
            raise _fail("a recorded bound differs from the candidate", check=check)


def _open(check: Check, *, rule: RuleQuery) -> bool:
    """Return whether the recorded bounds leave a window date open.

    An ``earliest`` bound that is undecided keeps it closed; an undecided
    ``latest`` keeps it open.
    """
    if rule.earliest is not None and (
        check.earliest is None
        or not compare_dates(Operator.LESS_THAN_OR_EQUAL, check.earliest, check.on)
    ):
        return False
    return check.latest is None or compare_dates(
        Operator.GREATER_THAN_OR_EQUAL, check.latest, check.on
    )


def _check_result(check: Check, *, rule: RuleQuery, trace: _Trace) -> None:
    if check.result is DecisionResult.OTHERWISE:
        return
    if check.result is DecisionResult.SKIPPED:
        if _open(check, rule=rule):
            raise _fail("a skipped record of an open window date", check=check)
        return
    if not _open(check, rule=rule):
        raise _fail("a test on a closed window date", check=check)
    result = _condition(rule, check=check, trace=trace)
    if result is not check.condition:
        raise _fail("the readings give another condition result", check=check)
    expected = DecisionResult.DECIDED if result is True else DecisionResult.NOT_MET
    if check.result is not expected:
        raise _fail("the condition gives another result", check=check)


def _condition(rule: RuleQuery, *, check: Check, trace: _Trace) -> bool | None:
    readings = {reading.name: reading for reading in check.readings}
    name = naming(model=trace.candidate, parameters=trace.parameters)

    def read(leaf: Expression) -> Quantity | DateValue | object:
        found = readings.get(leaf_name(leaf, name=name))
        if found is None:
            raise _fail(f"no reading of {leaf_name(leaf, name=name)}", check=check)
        return UNKNOWN if found.value is None else found.value

    for leaf in leaves(rule.condition):
        read(leaf)
    return truth(rule.condition, read=read, units=trace.units)  # type: ignore[arg-type]


def _check_reading(
    reading: Reading, *, check: Check, trace: _Trace, decided: set[UUID]
) -> None:
    if reading.available_on is not None and reading.available_on > check.on:
        raise _fail(f"{reading.name} is read before it is known", check=check)
    if reading.source is Source.DECIDED:
        _check_order_of_reading(reading, check=check, decided=decided)
    expected, known = _source_value(reading, check=check, trace=trace)
    if reading.value is None or expected is None:
        return
    if not _same(reading.value, expected, trace=trace):
        raise _fail(f"{reading.name} differs from its source", check=check)
    if known is not None and reading.available_on != known:
        raise _fail(f"{reading.name} has another availability date", check=check)


def _check_order_of_reading(
    reading: Reading, *, check: Check, decided: set[UUID]
) -> None:
    """Check that a decided value is read after its record, and only then."""
    if reading.value is None and reading.target in decided:
        raise _fail(f"{reading.name} was decided, not unknown", check=check)
    if reading.value is not None and reading.target not in decided:
        raise _fail(f"{reading.name} is read before its decision", check=check)


def _source_value(
    reading: Reading, *, check: Check, trace: _Trace
) -> tuple[Quantity | DateValue | None, date | None]:
    """Return the value that a reading's source holds, and when it is known."""
    target = reading.target
    if reading.source is Source.PATH:
        if target not in trace.path_amounts:
            raise _fail(f"{reading.name} is not in the path", check=check)
        return trace.path_amounts[target], trace.path_known[target]
    if reading.source is Source.PARAMETER:
        if reading.name not in trace.parameters:
            raise _fail(f"{reading.name} is not a parameter", check=check)
        return trace.parameters[reading.name], None
    if reading.source is Source.DECIDED:
        return _decided_value(reading, check=check, trace=trace)
    record = trace.candidate._index.records.get(target)
    if reading.source is Source.SOLVED and not isinstance(record, Movement):
        # A solved scalar reads the state of its date, not the final state.
        return None, None
    if target not in trace.values:
        raise _fail(f"{reading.name} is not in the candidate", check=check)
    known = known_on(record) if isinstance(record, Movement) else None
    return trace.values[target], known


def _decided_value(
    reading: Reading, *, check: Check, trace: _Trace
) -> tuple[Quantity | DateValue | None, date | None]:
    final = trace.finals.get(reading.target)
    if final is None:
        raise _fail(f"{reading.name} is not a decided value", check=check)
    return final.value, final.on


def _same(
    left: Quantity | DateValue,
    right: Quantity | DateValue | None,
    *,
    trace: _Trace,
) -> bool:
    if isinstance(left, Quantity) and isinstance(right, Quantity):
        converted = trace.units.convert(quantity=right, to=left.units).number
        return isclose(
            left.number, converted, rel_tol=trace.relative, abs_tol=trace.absolute
        )
    return left == right


def _check_final(rule: RuleQuery, *, checks: Sequence[Check], trace: _Trace) -> None:
    final = trace.finals[rule.target]
    if final.result is DecisionResult.DECIDED:
        expected = rule.then if rule.then is not None else final.on
    else:
        expected = rule.otherwise
        _check_otherwise(rule, final=final, checks=checks, trace=trace)
    if final.value is None or not _same(final.value, expected, trace=trace):
        raise _fail("the rule fixes another value", check=final)
    held = trace.values.get(rule.target)
    if held is None or not _same(final.value, held, trace=trace):
        raise _fail("the candidate does not hold the decided value", check=final)
    _check_complete(rule, final=final, checks=checks, trace=trace)


def _check_otherwise(
    rule: RuleQuery, *, final: Check, checks: Sequence[Check], trace: _Trace
) -> None:
    """Check that no window date of the rule remained when it took ``otherwise``."""
    later = _bound(rule.latest, trace=trace)
    if isinstance(later, date) and later < final.on:
        return
    if _bound(rule.earliest, trace=trace) is NEVER:
        return
    if rule.periods is not None and rule.periods[-1].end <= final.on:
        return
    window = calendar(rule, model=trace.candidate, path_known=trace.path_known)
    if any(item > final.on for item in window):
        raise _fail("otherwise while window dates remained", check=final)


def _check_complete(
    rule: RuleQuery, *, final: Check, checks: Sequence[Check], trace: _Trace
) -> None:
    """Check that each window date of the calendar before the decision has a record."""
    recorded = {check.on for check in checks if check.rule == rule.target}
    lowest = _literal(rule.earliest)
    highest = _literal(rule.latest)
    for item in calendar(rule, model=trace.candidate, path_known=trace.path_known):
        if item >= final.on:
            break
        if lowest is not None and item < lowest:
            continue
        if highest is not None and item > highest:
            continue
        if item not in recorded:
            raise _fail(f"no record of the window date {item}", check=final)


def _literal(node: Expression | None) -> date | None:
    if node is not None and node.kind is ExpressionKind.DATE:
        return node.date
    return None


def candidate_values(model: Model) -> Mapping[UUID, Quantity | DateValue]:
    """Return each scalar, date and Movement that a candidate holds."""
    found: dict[UUID, Quantity | DateValue] = {}
    for record in model._index.records.values():
        if isinstance(record, Value):
            _add_value(record, found)
    return found


def _add_value(value: Value, found: dict[UUID, Quantity | DateValue]) -> None:
    if value.kind is ValueKind.DATE:
        if value.never is not None:
            found[value.id] = NEVER
        elif value.date is not None:
            found[value.id] = value.date
    elif value.kind is ValueKind.MEASUREMENT and value.quantity is not None:
        found[value.id] = value.quantity
    elif value.kind is ValueKind.FLOW and value.flow is not None:
        for movement in value.flow.movements:
            if movement.magnitude is not None:
                found[movement.id] = Quantity(
                    magnitude=movement.magnitude, units=value.flow.units
                )


__all__ = [
    "Check",
    "Reading",
    "Source",
    "TraceFacts",
    "calendar",
    "candidate_values",
    "check_trace",
    "leaf_name",
    "naming",
]
