"""One rule as a query over a window (ADR-021): what the rule engine reads.

The module is internal. ``_declaration`` makes these from the public query and
from the stored ``Rule`` records.

``check_queries`` is the check of ADR-021 that needs no solve: a look-ahead, a
condition that reads a later rule, and a condition that reads a free input.
"""

from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from rangekeeper.duration import Period, PeriodTiming
from rangekeeper.duration.dates import DateValue
from rangekeeper.model import Model
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.text import parse, parse_condition
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.enums import ValueKind
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import (
    Constraint,
    Expression,
    ExpressionKind,
    Operator,
    Value,
)
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import AvailabilityError, ContractError


@dataclass(frozen=True, kw_only=True)
class RuleQuery:
    """The first window date on which a condition holds fixes one value.

    ``then`` is the value when the condition holds; without it, the window date
    itself. ``earliest`` and ``latest`` are inclusive date expressions.
    ``periods`` sets a calendar: the ``timing`` day of each Period. Without it, a
    window date is each date on which a value that the condition reads becomes
    known.
    """

    target: UUID
    condition: Expression
    otherwise: DateValue | Quantity
    then: DateValue | Quantity | None = None
    earliest: Expression | None = None
    latest: Expression | None = None
    periods: tuple[Period, ...] | None = None
    timing: PeriodTiming = PeriodTiming.FIRST


@dataclass(frozen=True, kw_only=True)
class Shift:
    """A condition's ``flow.shift(by=by)``: the Movement ``by`` Periods before."""

    flow: UUID
    by: int


def parameter_id(key: str) -> UUID:
    """Return the identity of the rule parameter with a key."""
    return uuid5(NAMESPACE_URL, f"rangekeeper:rule-parameter:{key}")


@dataclass(frozen=True, slots=True)
class _Symbol:
    """A Value or a rule parameter, as equation text names it."""

    id: UUID
    key: str
    kind: ValueKind | None
    units: str | None
    periods: tuple[Period, ...] | None = None


@dataclass(frozen=True, kw_only=True)
class _Names:
    """The names of a condition: the Model's Values and the rule parameters."""

    model: Model
    parameters: Mapping[str, Quantity]

    @property
    def units(self) -> UnitSystem:
        return self.model.unit_system

    def value(self, path: tuple[str, ...]) -> _Symbol:
        key = ".".join(path)
        if key in self.parameters:
            return _Symbol(
                id=parameter_id(key),
                key=key,
                kind=ValueKind.MEASUREMENT,
                units=self.parameters[key].units,
            )
        return _symbol(self.model.value(key=key), key=key)


def _symbol(value: Value, *, key: str) -> _Symbol:
    flow = value.flow
    if flow is None:
        return _Symbol(id=value.id, key=key, kind=value.kind, units=None)
    periods = tuple(m.period for m in flow.movements if m.period is not None)
    return _Symbol(
        id=value.id, key=key, kind=value.kind, units=flow.units, periods=periods
    )


def names_of(
    model: Model, *, parameters: Mapping[str, Quantity] | None = None
) -> _Names:
    """Return what equation text names: the Model's Values and the rule parameters."""
    return _Names(model=model, parameters=parameters or {})


def parse_text(
    *, text: str, model: Model, parameters: Mapping[str, Quantity] | None = None
) -> Expression:
    """Return the Expression of a condition or a bound, in equation text.

    Names are the Values of ``model`` and the keys of ``parameters``.
    """
    return parse(text=text, names=names_of(model, parameters=parameters))


def parse_condition_text(
    *, text: str, model: Model, parameters: Mapping[str, Quantity] | None = None
) -> Expression:
    """Return the Expression of a condition, where ``==`` tests a value."""
    return parse_condition(text=text, names=names_of(model, parameters=parameters))


def leaves(condition: Expression) -> Iterator[Expression]:
    """Yield what a condition reads: each reference and each call, in text order."""
    if condition.kind in (ExpressionKind.REFERENCE, ExpressionKind.CALL):
        yield condition
        return
    if condition.operand is not None:
        yield from leaves(condition.operand)
    for operand in condition.operands or ():
        yield from leaves(operand)


def shift_of(leaf: Expression) -> Shift | None:
    """Return the Flow and the number of Periods of a ``shift`` call, else None."""
    call = leaf.call
    if leaf.kind is not ExpressionKind.CALL or call is None:
        return None
    function = functions.get(call.function)
    if function is None or function.name != "shift":
        return None
    flow = (call.arguments or (None,))[0]
    by = next(
        (item.expression for item in call.named_arguments or () if item.name == "by"),
        None,
    )
    periods = None if by is None else _whole(by)
    if flow is None or flow.target is None or periods is None:
        raise ContractError(
            "a condition shifts a Flow Value by a whole number of Periods",
            code=Code.RULE_CAPABILITY,
            targets=(leaf.id,),
        )
    return Shift(flow=flow.target.target, by=periods)


def _whole(node: Expression) -> int | None:
    """Return a literal whole number, with its sign, else None."""
    if node.kind is ExpressionKind.QUANTITY and node.quantity is not None:
        return int(node.quantity.number)
    if node.operator is Operator.NEGATE and node.operand is not None:
        found = _whole(node.operand)
        return None if found is None else -found
    return None


def read_targets(condition: Expression) -> tuple[UUID, ...]:
    """Return the Value that each leaf of a condition reads, without repeats."""
    found: dict[UUID, None] = {}
    for leaf in leaves(condition):
        shift = shift_of(leaf)
        if shift is not None:
            found[shift.flow] = None
        elif leaf.target is not None:
            found[leaf.target.target] = None
    return tuple(found)


def references(node: Expression) -> frozenset[UUID]:
    """Return the Values and Movements that an Expression refers to."""
    return frozenset(
        child.target.target
        for child, _, _ in walk(node)
        if isinstance(child, Expression)
        and child.kind is ExpressionKind.REFERENCE
        and child.target is not None
    )


def definitions(model: Model) -> Mapping[UUID, frozenset[UUID]]:
    """Return what the equations of a Model define each Value from.

    ``x = e`` defines ``x`` from the references of ``e``. An equation with no
    single reference on a side defines each reference from the others.
    """
    records = model._index.records
    found: dict[UUID, frozenset[UUID]] = {}
    for record in records.values():
        if not isinstance(record, Constraint):
            continue
        predicate = records[record.predicate]
        assert isinstance(predicate, Expression)
        for target, source in _defined(predicate):
            found[target] = found.get(target, frozenset()) | source
    return found


def _defined(predicate: Expression) -> Iterator[tuple[UUID, frozenset[UUID]]]:
    """Yield each Value that an equation defines, with what it reads."""
    if (
        predicate.kind is not ExpressionKind.BINARY
        or predicate.operator is not Operator.EQUAL
    ):
        return
    left, right = predicate.operands or (None, None)
    assert left is not None and right is not None
    if left.kind is ExpressionKind.REFERENCE and left.target is not None:
        yield left.target.target, references(right)
    elif right.kind is ExpressionKind.REFERENCE and right.target is not None:
        yield right.target.target, references(left)
    else:
        every = references(predicate)
        for target in every:
            yield target, every - {target}


def dependencies(
    target: UUID, *, defined: Mapping[UUID, frozenset[UUID]]
) -> frozenset[UUID]:
    """Return ``target`` and each Value that its definitions read, transitively."""
    found: set[UUID] = set()
    waiting = [target]
    while waiting:
        item = waiting.pop()
        if item not in found:
            found.add(item)
            waiting.extend(defined.get(item, ()))
    return frozenset(found)


def check_queries(
    *,
    rules: Sequence[RuleQuery],
    model: Model,
    fixed: Collection[UUID],
    parameters: Collection[str] = (),
) -> None:
    """Raise when a rule reads the future, a later rule or a free input.

    A shift to a later Movement raises AvailabilityError. A condition that
    refers to its own value or a later rule's, or reads a scalar that depends on
    one, raises ContractError with ``rule_order``. A condition that depends on a
    free input (a Value that no equation defines and ``fixed`` does not hold, by
    its UUID or its Movements' UUIDs) raises ContractError with
    ``rule_reads_unknown``, and so does a name that is neither a Value of ``model``
    nor one of the keys in ``parameters``. A rule may read a Flow that depends on a
    later rule: a decision cannot change the Movements of the past (ADR-021).
    """
    declared = frozenset(parameter_id(key) for key in parameters)
    defined = definitions(model)
    targets = {rule.target for rule in rules}
    unknown = _free_inputs(model, fixed=fixed, defined=defined) - targets
    if len(targets) != len(rules):
        raise ContractError(
            "a value has one rule; a later rule replaces it in the same position",
            code=Code.RULE_CAPABILITY,
        )
    for position, rule in enumerate(rules):
        later = {item.target for item in rules[position:]}
        _check_kind(rule, model=model)
        _check_reads(rule, model=model)
        _check_names(rule, model=model, parameters=declared)
        _check_look_ahead(rule, model=model)
        for read in read_targets(rule.condition):
            _check_read(
                read,
                rule=rule,
                model=model,
                later=later,
                reach=dependencies(read, defined=defined),
                unknown=unknown,
            )


def _check_kind(rule: RuleQuery, *, model: Model) -> None:
    """Check that a rule fixes a date with a date, and a quantity with a quantity."""
    value = model.value(id=rule.target)
    values = (rule.otherwise, rule.then if rule.then is not None else rule.otherwise)
    if value.kind is ValueKind.DATE:
        fits = not any(isinstance(item, Quantity) for item in values)
    else:
        # The window date is a date, so a quantity needs ``then``.
        fits = value.kind is ValueKind.MEASUREMENT and rule.then is not None
        fits = fits and all(isinstance(item, Quantity) for item in values)
    if not fits:
        raise ContractError(
            f"the rule for {model.key_of(rule.target)} gives another kind of value "
            "than its Value holds",
            code=Code.RULE_CAPABILITY,
            targets=(rule.target,),
        )


def _check_reads(rule: RuleQuery, *, model: Model) -> None:
    """Check that a condition reads only Values and ``flow.shift(by=)``."""
    for leaf in leaves(rule.condition):
        if leaf.kind is ExpressionKind.CALL and shift_of(leaf) is None:
            raise ContractError(
                f"the condition of the rule for {model.key_of(rule.target)} calls a "
                "function; a condition reads values and flow.shift(by=)",
                code=Code.RULE_CAPABILITY,
                targets=(rule.target,),
            )


def _check_names(rule: RuleQuery, *, model: Model, parameters: frozenset[UUID]) -> None:
    """Check that each name of a condition and of a bound exists."""
    reads = set(read_targets(rule.condition))
    for bound in (rule.earliest, rule.latest):
        if bound is not None:
            reads.update(references(bound))
    missing = tuple(
        token
        for token in reads
        if token not in parameters and token not in model._index.records
    )
    if missing:
        key = model.key_of(rule.target)
        raise ContractError(
            f"the rule for {key} reads a parameter that this Specification does "
            "not declare",
            code=Code.RULE_READS_UNKNOWN,
            targets=(rule.target, *missing),
            values={"key": key},
        )


def _check_look_ahead(rule: RuleQuery, *, model: Model) -> None:
    for leaf in leaves(rule.condition):
        shift = shift_of(leaf)
        if shift is not None and shift.by < 0:
            raise AvailabilityError(
                f"the rule for {model.key_of(rule.target)} reads "
                f"{model.key_of(shift.flow)} {-shift.by} Periods ahead",
                key=model.key_of(rule.target),
            )


def _check_read(
    read: UUID,
    *,
    rule: RuleQuery,
    model: Model,
    later: set[UUID],
    reach: frozenset[UUID],
    unknown: frozenset[UUID],
) -> None:
    key = model.key_of(rule.target)
    if read in later or (not _is_flow(model, read) and reach & later):
        raise ContractError(
            f"the rule for {key} reads a value that it or a later rule decides; "
            "fix the rule that it reads first",
            code=Code.RULE_ORDER,
            targets=(rule.target, read),
            values={"key": key},
        )
    if reach & unknown:
        raise ContractError(
            f"the rule for {key} reads a value that depends on a free input",
            code=Code.RULE_READS_UNKNOWN,
            targets=(rule.target, read),
            values={"key": key},
        )


def _is_flow(model: Model, target: UUID) -> bool:
    record = model._index.records.get(target)
    return isinstance(record, Value) and record.kind is ValueKind.FLOW


def _free_inputs(
    model: Model, *, fixed: Collection[UUID], defined: Mapping[UUID, frozenset[UUID]]
) -> frozenset[UUID]:
    """Return each Value that no equation defines and ``fixed`` does not fix."""
    given = set(fixed)
    found = set()
    for record in model._index.records.values():
        if not isinstance(record, Value) or record.id in defined:
            continue
        if record.flow is not None:
            tokens = {movement.id for movement in record.flow.movements}
        else:
            tokens = {record.id}
        if tokens - given:
            found.add(record.id)
    return frozenset(found)


__all__ = [
    "RuleQuery",
    "Shift",
    "check_queries",
    "definitions",
    "dependencies",
    "leaves",
    "names_of",
    "parameter_id",
    "parse_condition_text",
    "parse_text",
    "read_targets",
    "references",
    "shift_of",
]
