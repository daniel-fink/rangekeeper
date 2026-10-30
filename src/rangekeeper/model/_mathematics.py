"""The Formulations of a ModelDraft and the equations of the next revision.

An entity's default Formulation is the root Formulation whose code is the
entity's path: its code, or its UUID when it has no code. A named Formulation,
such as "Funding", is a child of the default Formulation, with that name. Names
are unique among the named Formulations of one entity. ``ModelDraft.commit()``
takes the Formulation records from ``formulations()``.

``Mathematics`` holds every equation of the next revision: those of the draft's
Model and those that the draft adds. The draft can replace and remove them by
their Constraint UUID. A Formulation whose equations change keeps a working copy
of its root Expressions and Constraints, which ``formulations()`` builds into
its record.
"""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from difflib import get_close_matches
from typing import TypeVar
from uuid import UUID

from rangekeeper.model.equations import nodes
from rangekeeper.schema.records import Constraint, Expression, Formulation
from rangekeeper.schema.runtime import UNSET, Unset
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    ContractError,
    MissingReferenceError,
)

# Make the UUID of a record from the parts of its path, as ModelDraft._identify does.
Identify = Callable[..., UUID]
# Find an Expression of the draft's Model by its UUID: a root or a nested node.
Lookup = Callable[[UUID], Expression]
# The items of the working lists of a Formulation.
_Item = TypeVar("_Item", Expression, Constraint)


@dataclass(frozen=True, slots=True)
class Located:
    """One equation of the next revision: its Formulation, Constraint and predicate.

    ``path`` is the code of its root Formulation: the path of the entity whose
    default Formulation holds it, or None for a root Formulation with no code.
    """

    path: str | None
    formulation: Formulation
    constraint: Constraint
    predicate: Expression


@dataclass(slots=True)
class _Contents:
    """The working root Expressions and Constraints of one changed Formulation."""

    expressions: list[Expression]
    constraints: list[Constraint]


class Mathematics:
    """The draft's Formulations, the named Formulations it adds and its equations."""

    __slots__ = ("_roots", "_children", "_contents", "_dropped", "_identify", "_lookup")
    _roots: list[Formulation]
    # The named Formulations that the draft adds, by the UUID of their parent.
    _children: dict[UUID, list[Formulation]]
    # The working equations of each Formulation that the draft changes.
    _contents: dict[UUID, _Contents]
    # Whether the draft removed the Formulations of an entity.
    _dropped: bool
    _identify: Identify
    _lookup: Lookup

    def __init__(
        self,
        *,
        roots: Sequence[Formulation],
        identify: Identify,
        lookup: Lookup,
    ) -> None:
        self._roots = list(roots)
        self._children = {}
        self._contents = {}
        self._dropped = False
        self._identify = identify
        self._lookup = lookup

    @property
    def changed(self) -> bool:
        """Whether the draft added, changed or removed a Formulation or an equation."""
        return bool(self._children or self._contents or self._dropped)

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

    def add(
        self,
        *,
        formulation: UUID,
        path: str,
        equations: Sequence[tuple[str | None, Expression]],
    ) -> None:
        """Add equations to a Formulation of an entity, each with a new Constraint.

        Each equation has its key, the code of its Constraint. The Constraint
        UUID comes from the entity's path and the key; an equation with no key
        takes it from its Expression.
        """
        contents = self._open(formulation)
        for key, expression in equations:
            identity = (
                self._identify("constraint", str(expression.id))
                if key is None
                else self._identify("constraint", path, key)
            )
            contents.expressions.append(expression)
            contents.constraints.append(
                Constraint(
                    id=identity,
                    code=UNSET if key is None else key,
                    predicate=expression.id,
                )
            )

    def located(self, path: str) -> list[Located]:
        """Return the equations of an entity, in the order of its Formulations."""
        root = self._root(path)
        if root is None:
            return []
        return list(self._located(root))

    def replace(self, *, located: Located, predicate: Expression) -> None:
        """Replace the predicate of an equation; it keeps its Constraint UUID and code."""
        contents = self._open(located.formulation.id)
        index = _position(contents.constraints, located.constraint.id)
        contents.constraints[index] = located.constraint.replace(predicate=predicate.id)
        contents.expressions.append(predicate)
        self._prune(contents, located.constraint.predicate)

    def remove(self, *, located: Located) -> None:
        """Remove an equation: its Constraint, and its Expression when nothing uses it."""
        contents = self._open(located.formulation.id)
        del contents.constraints[_position(contents.constraints, located.constraint.id)]
        self._prune(contents, located.constraint.predicate)

    def drop(self, path: str) -> tuple[Formulation, ...]:
        """Remove the default Formulation of an entity and its named Formulations.

        Return the Formulations removed, as they were before the draft changed them.
        """
        root = self._root(path)
        if root is None:
            return ()
        removed = tuple(self._walk(root))
        for item in removed:
            self._children.pop(item.id, None)
            self._contents.pop(item.id, None)
        self._roots = [item for item in self._roots if item is not root]
        self._dropped = True
        return removed

    def predicates(self) -> Iterator[Located]:
        """Yield each equation of the next revision, in the order of its Formulations."""
        for root in self._roots:
            yield from self._located(root)

    def _located(self, root: Formulation) -> Iterator[Located]:
        for item in self._walk(root):
            for constraint, predicate in self._equations(item):
                yield Located(
                    path=root.code,
                    formulation=item,
                    constraint=constraint,
                    predicate=predicate,
                )

    def formulations(self) -> tuple[Formulation, ...]:
        """Return the root Formulations, with the Formulations and equations changed."""
        return tuple(self._built(record) for record in self._roots)

    def _root(self, path: str) -> Formulation | None:
        return next((item for item in self._roots if item.code == path), None)

    def _named(self, parent: UUID) -> list[Formulation]:
        root = next(item for item in self._roots if item.id == parent)
        return [*(root.formulations or ()), *self._children.get(parent, ())]

    def _walk(self, record: Formulation) -> Iterator[Formulation]:
        """Yield a Formulation and each Formulation under it, depth first."""
        yield record
        for child in (*(record.formulations or ()), *self._children.get(record.id, ())):
            yield from self._walk(child)

    def _find(self, identity: UUID) -> Formulation:
        for root in self._roots:
            for item in self._walk(root):
                if item.id == identity:
                    return item
        raise MissingReferenceError(identity, kind="Formulation", where="ModelDraft")

    def _open(self, identity: UUID) -> _Contents:
        """Return the working equations of a Formulation; copy them on first use."""
        contents = self._contents.get(identity)
        if contents is None:
            record = self._find(identity)
            contents = self._contents[identity] = _Contents(
                expressions=list(record.expressions or ()),
                constraints=list(record.constraints or ()),
            )
        return contents

    def _equations(
        self, record: Formulation
    ) -> Iterator[tuple[Constraint, Expression]]:
        """Yield the Constraints of a Formulation, each with its predicate."""
        contents = self._contents.get(record.id)
        if contents is None:
            constraints = record.constraints or ()
            roots = {item.id: item for item in record.expressions or ()}
        else:
            constraints = tuple(contents.constraints)
            roots = {item.id: item for item in contents.expressions}
        for constraint in constraints:
            found = roots.get(constraint.predicate)
            yield (
                constraint,
                (self._lookup(constraint.predicate) if found is None else found),
            )

    def _prune(self, contents: _Contents, predicate: UUID) -> None:
        """Remove the root Expression that held ``predicate`` when no equation uses it."""
        for index, root in enumerate(contents.expressions):
            held = set(nodes(root))
            if predicate not in held:
                continue
            used = any(item.constraint.predicate in held for item in self.predicates())
            if not used:
                del contents.expressions[index]
            return

    def _built(self, record: Formulation) -> Formulation:
        """Return a Formulation with what the draft changed in it and its children."""
        before = tuple(record.formulations or ())
        children = tuple(
            self._built(child)
            for child in (*before, *self._children.get(record.id, ()))
        )
        if len(children) != len(before) or any(
            new is not old for new, old in zip(children, before, strict=False)
        ):
            record = record.replace(formulations=children)
        contents = self._contents.get(record.id)
        if contents is not None:
            record = record.replace(
                expressions=_listed(contents.expressions, before=record.expressions),
                constraints=_listed(contents.constraints, before=record.constraints),
            )
        return record


def _listed(
    items: Sequence[_Item],
    *,
    before: Sequence[_Item] | None,
) -> tuple[_Item, ...] | Unset:
    """Return a working list as a record field: absent when it was and stays empty."""
    if not items and before is None:
        return UNSET
    return tuple(items)


def _position(constraints: Sequence[Constraint], identity: UUID) -> int:
    return next(index for index, item in enumerate(constraints) if item.id == identity)
