"""The Formulations of a ModelDraft and the equations that the draft adds to them.

An entity's default Formulation is the root Formulation whose code is the
entity's path: its code, or its UUID when it has no code. A named Formulation,
such as "Funding", is a child of the default Formulation, with that name. Names
are unique among the named Formulations of one entity. ``ModelDraft.commit()``
takes the Formulation records from ``formulations()``.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from difflib import get_close_matches
from uuid import UUID

from rangekeeper.schema.records import Constraint, Expression, Formulation
from rangekeeper.schema.runtime import UNSET
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    ContractError,
    MissingReferenceError,
)

# Make the UUID of a record from the parts of its path, as ModelDraft._identify does.
Identify = Callable[..., UUID]


@dataclass(frozen=True, slots=True)
class Equation:
    """One equation that a draft adds: its Boolean Expression and its Constraint."""

    expression: Expression
    constraint: Constraint


class Mathematics:
    """The draft's Formulations, the named Formulations it adds and its equations."""

    __slots__ = ("_roots", "_children", "_pending", "_identify")
    _roots: list[Formulation]
    # The named Formulations that the draft adds, by the UUID of their parent.
    _children: dict[UUID, list[Formulation]]
    # The equations that the draft adds, by the UUID of their Formulation.
    _pending: dict[UUID, list[Equation]]
    _identify: Identify

    def __init__(self, *, roots: Sequence[Formulation], identify: Identify) -> None:
        self._roots = list(roots)
        self._children = {}
        self._pending = {}
        self._identify = identify

    @property
    def changed(self) -> bool:
        """Whether the draft added a Formulation or an equation."""
        return bool(self._children or self._pending)

    def default(self, path: str) -> UUID:
        """Return the UUID of the default Formulation of an entity; make it if absent."""
        root = self._root(path)
        if root is None:
            root = Formulation(id=self._identify("formulation", path), code=path)
            self._roots.append(root)
        return root.id

    def add_named(
        self,
        *,
        path: str,
        name: str,
        description: str | None,
        where: str,
    ) -> UUID:
        """Declare a named Formulation of an entity, and return its UUID.

        A name that the entity's named Formulations have raises ContractError
        with the code UNIQUE.
        """
        parent = self.default(path)
        if any(item.name == name for item in self._named(parent)):
            raise ContractError(
                f"Formulation name {name!r} is already declared in {where}",
                code=Code.UNIQUE,
                values={"kind": "Formulation", "name": name, "where": where},
            )
        record = Formulation(
            id=self._identify("formulation", path, name),
            name=name,
            description=UNSET if description is None else description,
        )
        self._children.setdefault(parent, []).append(record)
        return record.id

    def named(self, *, path: str, name: str, where: str) -> UUID:
        """Return the UUID of the one named Formulation of an entity with this name.

        No match raises MissingReferenceError with the nearest names; several
        matches raise AmbiguousReferenceError with their UUIDs.
        """
        root = self._root(path)
        records = [] if root is None else self._named(root.id)
        matches = [item for item in records if item.name == name]
        if len(matches) == 1:
            return matches[0].id
        if matches:
            raise AmbiguousReferenceError(
                name,
                kind="Formulation",
                by="name",
                where=where,
                candidates=[str(item.id) for item in matches],
            )
        names = sorted({item.name for item in records if item.name is not None})
        raise MissingReferenceError(
            name,
            kind="Formulation",
            by="name",
            where=where,
            candidates=get_close_matches(name, names, n=3),
        )

    def add(self, *, formulation: UUID, expressions: Sequence[Expression]) -> None:
        """Add equations to a Formulation, each with a new Constraint."""
        self._pending.setdefault(formulation, []).extend(
            Equation(
                expression=expression,
                constraint=Constraint(
                    id=self._identify("constraint", str(expression.id)),
                    predicate=expression.id,
                ),
            )
            for expression in expressions
        )

    def formulations(self) -> tuple[Formulation, ...]:
        """Return the root Formulations, with the Formulations and equations added."""
        return tuple(self._built(record) for record in self._roots)

    def _root(self, path: str) -> Formulation | None:
        return next((item for item in self._roots if item.code == path), None)

    def _named(self, parent: UUID) -> list[Formulation]:
        root = next(item for item in self._roots if item.id == parent)
        return [*(root.formulations or ()), *self._children.get(parent, ())]

    def _built(self, record: Formulation) -> Formulation:
        """Return a Formulation with what the draft added to it and its children."""
        before = tuple(record.formulations or ())
        children = tuple(
            self._built(child)
            for child in (*before, *self._children.get(record.id, ()))
        )
        if len(children) != len(before) or any(
            new is not old for new, old in zip(children, before, strict=False)
        ):
            record = record.replace(formulations=children)
        equations = self._pending.get(record.id, ())
        if equations:
            record = record.replace(
                expressions=(
                    *(record.expressions or ()),
                    *(item.expression for item in equations),
                ),
                constraints=(
                    *(record.constraints or ()),
                    *(item.constraint for item in equations),
                ),
            )
        return record
