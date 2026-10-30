"""The values that a draft's equations define without a declaration (D44).

Equation text can name a key that its entity does not declare, when an equation
of the same call, or of an earlier call of the draft, defines the key: one side
of an equality is the key alone, as in ``"works = a_works + b_works"``. The
draft reserves a UUID for each such value. ``commit()`` works out the kind and
units of each one from the equations that define it, with the dimensional
analysis of ``model._dimensions``, and adds a Value record for it: a date; a
Flow when its definition references a whole Flow; or else a measurement. A
value whose units cannot be worked out stops the commit.
"""

import re
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from difflib import get_close_matches
from uuid import UUID

from rangekeeper.flow import Flow, Movement
from rangekeeper.model._dimensions import (
    Dimension,
    Inference,
    Kind,
    Lookup,
    of_value,
)
from rangekeeper.quantity import UnitSystem
from rangekeeper.schema.enums import ExpressionKind, Operator, ValueKind
from rangekeeper.schema.records import Expression, Measure, Value
from rangekeeper.schema.runtime import UNSET, Unset
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import (
    EquationError,
    MissingReferenceError,
    ValidationError,
)


@dataclass(frozen=True, slots=True)
class Place:
    """The entity that owns an undeclared value."""

    id: UUID
    # The entity in an error, such as "Entity project".
    where: str
    # The code path of the entity, for the identities of a Flow's Movements.
    path: str


@dataclass(frozen=True, slots=True)
class Pending:
    """A value that an equation defines and no call declares: its owner, key and UUID.

    ``previous`` is the Value of an earlier revision whose units were inferred,
    which the draft works out again; it is None for a new value.
    """

    place: Place
    key: str
    id: UUID
    previous: Value | None = None


@dataclass(frozen=True, slots=True)
class Unknown:
    """The symbol of a value that an equation defines, in equation text.

    Its kind and units are not known until ``commit()`` works them out, so the
    Terms that reference it have no kind or units yet.
    """

    id: UUID
    key: str
    kind: None = None
    units: None = None
    periods: None = None


class Undeclared:
    """The values of a draft that its equations define without a declaration."""

    __slots__ = ("_pending", "_again")
    _pending: dict[tuple[UUID, str], Pending]
    # The inferred Values of the draft's Model, which it works out again.
    _again: list[Pending]

    def __init__(self) -> None:
        self._pending = {}
        self._again = []

    def __iter__(self) -> Iterator[Pending]:
        return iter((*self._pending.values(), *self._again))

    def __bool__(self) -> bool:
        return bool(self._pending or self._again)

    def again(self, *, place: Place, value: Value) -> None:
        """Work out the units of an inferred Value of the Model again at commit."""
        self._again.append(
            Pending(place=place, key=value.key, id=value.id, previous=value)
        )

    def get(self, owner: UUID, key: str) -> UUID | None:
        """Return the UUID of an undeclared value of an owner, or None."""
        found = self._pending.get((owner, key))
        return None if found is None else found.id

    def keys(self, owner: UUID) -> list[str]:
        """Return the undeclared keys of an owner, in the order of their equations."""
        return [key for item, key in self._pending if item == owner]

    def add(
        self,
        *,
        place: Place,
        new: Mapping[str, UUID],
        equations: Sequence[Expression],
        texts: Sequence[str],
        candidates: Sequence[str],
    ) -> None:
        """Reserve the new values of one call of ``equations``, each defined there.

        A new key that no equation of the call defines raises EquationError,
        as a key that is not declared, with the nearest ``candidates``.
        """
        defined = {target for item in equations for target, _ in definitions_in(item)}
        names = [*candidates, *(key for key, id in new.items() if id in defined)]
        for key, identity in new.items():
            if identity not in defined:
                raise _undefined(key, where=place.where, texts=texts, candidates=names)
        for key, identity in new.items():
            self._pending[(place.id, key)] = Pending(place=place, key=key, id=identity)

    def declare(self, owner: UUID, key: str) -> UUID | None:
        """Return the UUID of an undeclared value that a call now declares, or None.

        The declaration keeps the UUID that the equations reference, and the
        value is no longer undeclared.
        """
        found = self._pending.pop((owner, key), None)
        return None if found is None else found.id

    def values(
        self,
        *,
        equations: Sequence[Expression],
        units: UnitSystem,
        lookup: Lookup,
        measure: Callable[[str], Measure],
        known: Sequence[str],
        identify: Callable[..., UUID],
    ) -> dict[UUID, list[Value]]:
        """Return a Value record for each undeclared value, by the UUID of its owner.

        Each record has ``inferred=True``. A Value that the draft works out
        again keeps its UUID and description. ``measure`` gives the Measure of
        units text, and ``known`` the units texts in the order of their
        Measures; a quantity takes the first of them that is compatible with
        its units. A Flow with known Periods has one unresolved Movement in
        each, with an identity from ``identify``, or the identity of the
        previous Movement of that Period. A value whose units cannot be worked
        out raises ValidationError, with one issue for each such value.
        """
        found = self.infer(equations=equations, units=units, lookup=lookup)
        added: dict[UUID, list[Value]] = {}
        for item in self:
            dimension = found[item.id]
            description: str | Unset = UNSET
            if item.previous is not None and item.previous.description is not None:
                description = item.previous.description
            if dimension.kind is Kind.DATE:
                value = Value(
                    id=item.id,
                    key=item.key,
                    kind=ValueKind.DATE,
                    description=description,
                    inferred=True,
                )
            else:
                assert dimension.units is not None  # a quantity has units
                text = spelled(dimension.units, units=units, known=known)
                value = Value(
                    id=item.id,
                    key=item.key,
                    kind=ValueKind.FLOW if dimension.flow else ValueKind.MEASUREMENT,
                    measure=measure(text).id,
                    description=description,
                    flow=_shape(item, dimension, units=text, identify=identify),
                    inferred=True,
                )
            added.setdefault(item.place.id, []).append(value)
        return added

    def infer(
        self,
        *,
        equations: Sequence[Expression],
        units: UnitSystem,
        lookup: Lookup,
    ) -> dict[UUID, Dimension]:
        """Return the Dimension of each undeclared value, from its definitions.

        A definition gives its value the Dimension of its other side once that
        is known, so one definition can use another. A value whose Dimension
        stays unknown raises ValidationError, with one issue for each.
        """
        ids = {item.id for item in self}
        definitions = [
            (target, side)
            for equation in equations
            for target, side in definitions_in(equation)
            if target in ids
        ]
        found: dict[UUID, Dimension] = {}
        analysis = Inference(
            units=units,
            lookup=lambda identity: found.get(identity) or lookup(identity),
        )
        while _step(analysis, definitions, found):
            pass
        missing = [item for item in self if item.id not in found]
        if missing:
            issues = tuple(_unknown(item) for item in missing)
            raise ValidationError(ValidationReport(issues))
        return found


def _step(
    analysis: Inference,
    definitions: Sequence[tuple[UUID, Expression]],
    found: dict[UUID, Dimension],
) -> bool:
    """Give each value whose definition is now known its Dimension; return any progress."""
    progress = False
    for target, side in definitions:
        if target in found:
            continue
        dimension = analysis.dimension(side)
        if dimension is not None and dimension.kind is not Kind.BOOLEAN:
            found[target] = dimension
            progress = True
    return progress


def _shape(
    item: Pending,
    dimension: Dimension,
    *,
    units: str,
    identify: Callable[..., UUID],
) -> Flow | Unset:
    """Return the Flow shape of an inferred Flow with known Periods, or UNSET."""
    if not dimension.flow or not dimension.periods:
        return UNSET
    before = item.previous.flow if item.previous is not None else None
    kept = {
        movement.period: movement.id
        for movement in (() if before is None else before.movements)
        if movement.period is not None
    }
    return Flow(
        units=units,
        movements=[
            Movement(
                id=kept.get(period)
                or identify(
                    "movement", item.place.path, item.key, period.start.isoformat()
                ),
                period=period,
            )
            for period in dimension.periods
        ],
    )


def definitions_in(equation: Expression) -> Iterator[tuple[UUID, Expression]]:
    """Yield each value that an equality defines, with the other side.

    An equality defines a value when one of its sides is a reference to the
    whole value: ``works = a_works + b_works`` defines ``works``.
    """
    if (
        equation.kind is not ExpressionKind.BINARY
        or equation.operator is not Operator.EQUAL
        or equation.operands is None
    ):
        return
    left, right = equation.operands
    for side, other in ((left, right), (right, left)):
        if side.kind is ExpressionKind.REFERENCE and side.target is not None:
            yield side.target.target, other


def known_values(
    values: Iterable[Value],
    *,
    measures: Sequence[Measure],
) -> Lookup:
    """Return the Dimension of each declared Value and Movement, by its UUID."""
    units = {item.id: item.units for item in measures}
    found: dict[UUID, Dimension | None] = {}
    for value in values:
        found[value.id] = of_value(
            value, units=None if value.measure is None else units.get(value.measure)
        )
        flow = value.flow
        if flow is not None:
            for movement in flow.movements:
                found[movement.id] = Dimension(kind=Kind.QUANTITY, units=flow.units)
    return found.get


def spelled(text: str, *, units: UnitSystem, known: Sequence[str]) -> str:
    """Return the units text for a value: the first compatible known text, if any.

    ``AUD * per_annum`` is spelled ``AUD pa`` when a Measure has those units.
    Without a compatible known text, a ratio is ``ratio``, and other units keep
    their canonical text.
    """
    for item in known:
        if units.compatible(text, item):
            return item
    if units.compatible(text, "ratio"):
        return "ratio"
    return units.canonical(units=text)


def _undefined(
    key: str,
    *,
    where: str,
    texts: Sequence[str],
    candidates: Sequence[str],
) -> EquationError:
    """Return the error for a key that is not declared and that no equation defines."""
    missing = MissingReferenceError(
        key,
        kind="Value",
        by="key",
        where=where,
        candidates=get_close_matches(key, sorted(candidates), n=3),
    )
    pattern = re.compile(rf"(?<![\w.]){re.escape(key)}(?!\w)")
    for text in texts:
        match = pattern.search(text)
        if match is not None:
            break
    else:
        text, match = (texts[0] if texts else key), None
    start, end = (0, len(text)) if match is None else match.span()
    return EquationError(
        f"{missing}; declare it, or define it with an equation such as '{key} = ...'",
        code=Code.REFERENCE_MISSING,
        text=text,
        start=start,
        end=end,
        suggestions=missing.candidates,
    )


def _unknown(item: Pending) -> Issue:
    return Issue(
        Code.UNITS,
        f"the units of {item.key!r} in {item.place.where} cannot be worked out from "
        f"its equations; declare it with its units, such as "
        f"value(key={item.key!r}, units=...)",
        targets=(item.id,),
        values={"key": item.key, "where": item.place.where},
    )
