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

from rangekeeper.model._dimensions import (
    Analysis,
    Dimension,
    Kind,
    Lookup,
    of_value,
)
from rangekeeper.quantity import UnitSystem
from rangekeeper.schema.enums import ExpressionKind, Operator, ValueKind
from rangekeeper.schema.records import Expression, Measure, Value
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import (
    EquationError,
    MissingReferenceError,
    ValidationError,
)


@dataclass(frozen=True, slots=True)
class Pending:
    """A value that an equation defines and no call declares: its owner, key and UUID."""

    owner: UUID
    key: str
    id: UUID
    # The owner in an error, such as "Entity project".
    where: str


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


class Undeclared:
    """The values of a draft that its equations define without a declaration."""

    __slots__ = ("_pending",)
    _pending: dict[tuple[UUID, str], Pending]

    def __init__(self) -> None:
        self._pending = {}

    def __iter__(self) -> Iterator[Pending]:
        return iter(tuple(self._pending.values()))

    def __bool__(self) -> bool:
        return bool(self._pending)

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
        owner: UUID,
        where: str,
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
                raise _undefined(key, where=where, texts=texts, candidates=names)
        for key, identity in new.items():
            self._pending[(owner, key)] = Pending(
                owner=owner, key=key, id=identity, where=where
            )

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
    ) -> dict[UUID, list[Value]]:
        """Return a Value record for each undeclared value, by the UUID of its owner.

        ``measure`` gives the Measure of units text, and ``known`` the units
        texts in the order of their Measures; a quantity takes the first of
        them that is compatible with its units. A value whose units cannot be
        worked out raises ValidationError, with one issue for each such value.
        """
        found = self.infer(equations=equations, units=units, lookup=lookup)
        added: dict[UUID, list[Value]] = {}
        for item in self:
            dimension = found[item.id]
            if dimension.kind is Kind.DATE:
                value = Value(id=item.id, key=item.key, kind=ValueKind.DATE)
            else:
                assert dimension.units is not None  # a quantity has units
                value = Value(
                    id=item.id,
                    key=item.key,
                    kind=ValueKind.FLOW if dimension.flow else ValueKind.MEASUREMENT,
                    measure=measure(
                        spelled(dimension.units, units=units, known=known)
                    ).id,
                )
            added.setdefault(item.owner, []).append(value)
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
        analysis = Analysis(
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
    analysis: Analysis,
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
        f"the units of {item.key!r} in {item.where} cannot be worked out from "
        f"its equations; declare it with its units, such as "
        f"value(key={item.key!r}, units=...)",
        targets=(item.id,),
        values={"key": item.key, "where": item.where},
    )
