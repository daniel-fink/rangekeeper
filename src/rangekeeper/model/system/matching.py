"""Evaluate a declarative ``Filter`` against the Entities of one pinned Model.

A test has three results: it passes, it fails, or its value is missing. An
Entity passes a Filter when every test passes. It fails when any test fails.
Otherwise a tested value is missing: the Entity does not pass, and the Match
counts it as missing (ADR-016). A
missing value is never zero.
"""

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from uuid import UUID

from rangekeeper.model import Entity, Label, Model, Value, ValueKind
from rangekeeper.model.definitions import _classes
from rangekeeper.model.system.errors import SelectionError
from rangekeeper.quantity import UnitSystem
from rangekeeper.schema.enums import ValueRelation
from rangekeeper.schema.records import Filter, Quantity, ValueTest
from rangekeeper.shared.amounts import number as _number

# The relative tolerance of equality, as in ``rangekeeper.quantity.isclose``.
_RELATIVE = 1e-9
_COMPARISONS = {
    ValueRelation.EQUAL,
    ValueRelation.NOT_EQUAL,
    ValueRelation.LESS,
    ValueRelation.LESS_OR_EQUAL,
    ValueRelation.GREATER,
    ValueRelation.GREATER_OR_EQUAL,
}

# One test of one Entity: True passes, False fails, None has a missing value.
Test = Callable[[Entity], bool | None]


@dataclass(frozen=True)
class Match:
    """Entities that pass a Filter, fail it, or have a missing tested value.

    The three tuples partition the tested Entities and keep their order.
    ``missing`` holds the Entities that no test failed but at least one could not
    decide, because its Value or Label is missing. They do not pass.
    """

    passed: tuple[UUID, ...]
    failed: tuple[UUID, ...]
    missing: tuple[UUID, ...]

    @property
    def complete(self) -> bool:
        """Whether every tested Entity was decided: none has a missing value."""
        return not self.missing


def _content(value: Value) -> object:
    if value.kind is ValueKind.MEASUREMENT:
        return value.quantity
    if value.kind is ValueKind.FLOW:
        return value.flow
    return value.content


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=_RELATIVE)


def _compare(relation: ValueRelation, left: float, right: float) -> bool:
    equal = _close(left, right)
    if relation is ValueRelation.EQUAL:
        return equal
    if relation is ValueRelation.NOT_EQUAL:
        return not equal
    if relation is ValueRelation.LESS:
        return left < right and not equal
    if relation is ValueRelation.LESS_OR_EQUAL:
        return left < right or equal
    if relation is ValueRelation.GREATER:
        return left > right and not equal
    return left > right or equal


def _value_test(model: Model, test: ValueTest, unit_system: UnitSystem) -> Test:
    relation, key = test.relation, test.key
    operands: tuple[Quantity, ...] = (
        (test.minimum, test.maximum)  # type: ignore[assignment]
        if relation is ValueRelation.BETWEEN
        else ()
        if test.quantity is None
        else (test.quantity,)
    )
    # Unknown units raise now, also when no Entity has the Value.
    for operand in operands:
        unit_system.validate_units(operand.units)

    def number(quantity: Quantity, units: str) -> float:
        return unit_system.convert(quantity, to=units).number

    def own(quantity: Quantity) -> float:
        return _number(quantity.magnitude)

    def run(entity: Entity) -> bool | None:
        value = model._local(Value, entity.id, key)
        content = None if value is None else _content(value)
        if relation is ValueRelation.PRESENT:
            return content is not None
        if relation is ValueRelation.MISSING:
            return content is None
        if value is not None and value.kind is not ValueKind.MEASUREMENT:
            raise SelectionError(
                f"Value {value.id} at {entity.id}/{key} is a {value.kind.value} "
                f"Value; a {relation.value} test needs a measurement Value"
            )
        if content is None:
            return None
        recorded: Quantity = content  # type: ignore[assignment]
        if relation is ValueRelation.BETWEEN:
            low, high = operands
            return _compare(
                ValueRelation.GREATER_OR_EQUAL,
                number(recorded, low.units),
                own(low),
            ) and _compare(
                ValueRelation.LESS_OR_EQUAL,
                number(recorded, high.units),
                own(high),
            )
        (operand,) = operands
        return _compare(relation, number(recorded, operand.units), own(operand))

    return run


def _tests(model: Model, condition: Filter, unit_system: UnitSystem) -> tuple:
    """Prepare each test once: resolve Classifications and check units."""
    definitions = model.definitions
    tests: list[Test] = []
    if condition.classification is not None:
        classes = _classes(
            definitions,
            condition.classification,
            exclusive=bool(condition.exclusive),
        )
        tests.append(lambda entity: entity.classification in classes)
    for criterion in condition.labels or ():
        allowed = _classes(
            definitions,
            criterion.classification,
            exclusive=bool(criterion.exclusive),
        )

        def label(entity: Entity, key=criterion.key, allowed=allowed) -> bool | None:
            found = model._local(Label, entity.id, key)
            if found is None:
                return None
            return any(item in allowed for item in found.classifications or ())

        tests.append(label)
    for test in condition.tests or ():
        tests.append(_value_test(model, test, unit_system))
    return tuple(tests)


def _prepare(
    model: Model,
    condition: Filter,
    *,
    unit_system: UnitSystem | None = None,
) -> Test:
    """Return the three-valued test of one Entity against ``condition``.

    The test returns True when the Entity passes, False when it fails, and None
    when no test fails but a tested value is missing. Classifications and units
    are checked once, here. Without ``unit_system``, the Model's is used.
    """
    if not isinstance(model, Model):
        raise TypeError("model must be a canonical Model")
    if not isinstance(condition, Filter):
        raise TypeError("condition must be a Filter")
    if unit_system is not None and not isinstance(unit_system, UnitSystem):
        raise TypeError("unit_system must be a UnitSystem")
    tests = _tests(
        model, condition, model.unit_system if unit_system is None else unit_system
    )

    def run(entity: Entity) -> bool | None:
        missing = False
        for test in tests:
            result = test(entity)
            if result is False:
                return False
            missing = missing or result is None
        return None if missing else True

    return run


def match(
    model: Model,
    entities: Iterable[Entity],
    condition: Filter,
    *,
    unit_system: UnitSystem | None = None,
) -> Match:
    """Test ``entities`` of ``model`` against ``condition``; see ``Match``."""
    test = _prepare(model, condition, unit_system=unit_system)
    passed: list[UUID] = []
    failed: list[UUID] = []
    missing: list[UUID] = []
    for entity in entities:
        result = test(model.entity(entity.id))
        (passed if result else failed if result is False else missing).append(entity.id)
    return Match(tuple(passed), tuple(failed), tuple(missing))


__all__ = ["Match", "match"]
