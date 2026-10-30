"""The equations of a Model revision: their keys, the keys that they use and their text.

``model.equations`` is an ``Equations`` collection with one ``Equation`` for
each Constraint of the revision, in the order of its Formulations: each root
Formulation, then its children, depth first. An equation's ``key`` names it
(D40): a draft gives each equation the key of the first value of its text, the
value on its left side in ``income = a_rent + b_rent``. Its ``keys`` are the
keys of every value that it uses, on either side. ``where`` selects equations
by these columns.
"""

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, overload
from uuid import UUID

from rangekeeper.flow import Movement
from rangekeeper.model.expression.rendering import render
from rangekeeper.schema.enums import ExpressionKind
from rangekeeper.schema.records import (
    Constraint,
    Entity,
    Expression,
    Formulation,
    Value,
)
from rangekeeper.shared.table import Row, Table

if TYPE_CHECKING:
    # The Model makes its equations and imports this module.
    from rangekeeper.model.model import Model

# The columns of ``Equations.table``.
EQUATION_COLUMNS = ("key", "text", "formulation", "entity")
# Name the Value or Movement that a reference targets, as equation text writes it.
Namer = Callable[[UUID], str]


@dataclass(frozen=True, kw_only=True, slots=True)
class Equation:
    """One equation of a Model revision: its key, the keys that it uses and its text.

    ``id`` is the UUID of its Constraint. ``key`` names the equation: the
    Constraint's code, which a draft gives each equation, or else the key of
    the first value of its text, such as ``income`` in
    ``income = a_rent + b_rent``; None for an equation that uses no value.
    ``keys`` are the keys of each value that it uses, on either side, once
    each in the order of its text; a value of another entity is written
    ``code.key``. ``text`` is the equation text, which reads back to the same
    records. ``formulation`` is the name of its named Formulation, or None for
    the default Formulation of its entity. ``entity`` is the code of the entity
    whose Formulations hold it, or None.
    """

    id: UUID
    key: str | None
    keys: tuple[str, ...]
    text: str
    formulation: str | None
    entity: str | None

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"<equation {self.text}>"


class Equations(Sequence[Equation]):
    """The equations of a Model revision, in Formulation order, with ``where``.

    ``model.equations`` returns one. It is a sequence of ``Equation`` values,
    and a notebook shows it as a table with the key, text, Formulation and
    entity of each equation. ``where`` returns the equations whose columns
    match (D40).
    """

    __slots__ = ("_items",)
    _items: tuple[Equation, ...]

    def __init__(self, equations: Iterable[Equation] = ()) -> None:
        items = tuple(equations)
        if not all(isinstance(item, Equation) for item in items):
            raise TypeError("Equations holds Equation values")
        self._items = items

    @overload
    def __getitem__(self, index: int) -> Equation: ...

    @overload
    def __getitem__(self, index: slice) -> "Equations": ...

    def __getitem__(self, index: int | slice) -> "Equation | Equations":
        if isinstance(index, slice):
            return Equations(self._items[index])
        return self._items[index]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Equation]:
        return iter(self._items)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Equations):
            return NotImplemented
        return self._items == other._items

    def __hash__(self) -> int:
        return hash(self._items)

    def where(
        self,
        *,
        key: str | Sequence[str] | None = None,
        keys: str | Sequence[str] | None = None,
        formulation: str | Sequence[str] | None = None,
        entity: str | Sequence[str] | None = None,
    ) -> "Equations":
        """Return the equations whose columns have these values, in the same order.

        Each argument names a column (D40). Text means equals, and a list of
        texts means any of them: ``where(key=["a_rent", "b_rent"])``. ``keys``
        holds several values, so ``where(keys="start_date")`` keeps each
        equation that uses ``start_date``, on either side. ``formulation`` is
        the name of a named Formulation, such as ``"Dates"``, and ``entity``
        an entity code. When several arguments are given, all must hold. A
        call with none raises TypeError.
        """
        tests = [
            (column, _wanted(value, column))
            for column, value in (
                ("key", key),
                ("keys", keys),
                ("formulation", formulation),
                ("entity", entity),
            )
            if value is not None
        ]
        if not tests:
            raise TypeError(
                "where takes at least one of key, keys, formulation, entity"
            )
        return Equations(
            item
            for item in self._items
            if all(_matches(item, column, wanted) for column, wanted in tests)
        )

    @property
    def table(self) -> Table:
        """A Table with one row for each equation: its key, text, Formulation and entity.

        Each row's id is the UUID of the equation's Constraint.
        """
        return Table(
            EQUATION_COLUMNS,
            [
                Row(
                    {
                        "key": item.key,
                        "text": item.text,
                        "formulation": item.formulation,
                        "entity": item.entity,
                    },
                    id=item.id,
                )
                for item in self._items
            ],
        )

    def _repr_html_(self) -> str:
        return self.table._repr_html_()

    def __repr__(self) -> str:
        if not self._items:
            return "Equations(0 equations)"
        count = len(self._items)
        lines = [f"Equations({count} equation{'' if count == 1 else 's'}):"]
        lines.extend(f"  {item.text}" for item in self._items)
        return "\n".join(lines)


def _wanted(value: str | Sequence[str], column: str) -> frozenset[str]:
    """Return the texts that a ``where`` argument accepts; raise TypeError for another type."""
    if isinstance(value, str):
        return frozenset((value,))
    if isinstance(value, Sequence) and all(isinstance(item, str) for item in value):
        return frozenset(value)
    raise TypeError(f"{column} must be text or a list of texts")


def _matches(item: Equation, column: str, wanted: frozenset[str]) -> bool:
    if column == "keys":
        return not wanted.isdisjoint(item.keys)
    return getattr(item, column) in wanted


def references(expression: Expression) -> Iterator[UUID]:
    """Yield the target of each reference of an expression, in the order of its text.

    The operands of an operation come in their order, and the arguments of a
    call in the order that equation text writes them: a method's Flow first.
    """
    if expression.kind is ExpressionKind.REFERENCE:
        assert expression.target is not None
        yield expression.target.target
    for operand in operands(expression):
        yield from references(operand)


def operands(expression: Expression) -> tuple[Expression, ...]:
    """Return the Expressions inside one node, in the order of its text."""
    if expression.operand is not None:
        return (expression.operand,)
    if expression.operands:
        return tuple(expression.operands)
    call = expression.call
    if call is not None:
        return (
            *(call.arguments or ()),
            *(item.expression for item in call.named_arguments or ()),
        )
    selection = expression.selection
    if selection is not None:
        index = () if selection.index is None else (selection.index,)
        return (selection.base, *index)
    return ()


def nodes(expression: Expression) -> Iterator[UUID]:
    """Yield the UUID of an expression and of each node inside it."""
    yield expression.id
    for operand in operands(expression):
        yield from nodes(operand)


def equation_of(
    constraint: Constraint,
    *,
    predicate: Expression,
    name: Namer,
    formulation: str | None,
    entity: str | None,
) -> Equation:
    """Return the Equation of a Constraint, with ``name`` for each value it uses."""
    keys = tuple(dict.fromkeys(name(target) for target in references(predicate)))
    return Equation(
        id=constraint.id,
        key=constraint.code if constraint.code is not None else default_key(keys),
        keys=keys,
        text=render(expression=predicate, name=lambda target: name(target.target)),
        formulation=formulation,
        entity=entity,
    )


def default_key(keys: Sequence[str]) -> str | None:
    """Return the key that names an equation by default: its first value, or None."""
    return keys[0] if keys else None


def equations_of(model: "Model") -> Equations:
    """Return the equations of a Model revision, in the order of its Formulations."""
    system = model.system
    if system is None:
        return Equations()
    owners = {
        record.code or str(record.id): record
        for record in model._index.records.values()
        if isinstance(record, Entity)
    }
    found: list[Equation] = []
    for root in system.formulations or ():
        entity = owners.get(root.code) if root.code is not None else None
        name = _namer(model, owner=None if entity is None else entity.id)
        for formulation, default in _walk(root):
            for constraint in formulation.constraints or ():
                found.append(
                    equation_of(
                        constraint,
                        predicate=model._index.get(constraint.predicate, Expression),
                        name=name,
                        formulation=None
                        if default and entity is not None
                        else formulation.name,
                        entity=None if entity is None else entity.code,
                    )
                )
    return Equations(found)


def _walk(root: Formulation) -> Iterator[tuple[Formulation, bool]]:
    """Yield a root Formulation and each Formulation under it, depth first."""
    yield root, True
    for child in root.formulations or ():
        for item, _ in _walk(child):
            yield item, False


def _namer(model: "Model", *, owner: UUID | None) -> Namer:
    """Return the name of each referenced value, as the equations of ``owner`` write it.

    A value of ``owner`` is its key and a value of another entity with a code
    that no other entity has is ``code.key``; another value is named by
    ``model.key_of``.
    """
    index = model._index

    def name(target: UUID) -> str:
        record = index.records.get(target)
        if isinstance(record, Movement):
            flow = index.owners[target]
            assert flow is not None  # a Movement belongs to its Flow Value
            record = index.records[flow]
        if not isinstance(record, Value):
            return str(target)
        holder = index.owners[record.id]
        if holder is not None and holder == owner:
            return record.key
        entity = None if holder is None else index.records.get(holder)
        code = entity.code if isinstance(entity, Entity) else None
        if code is not None and model._named.get((Entity, code)) == (holder,):
            return f"{code}.{record.key}"
        return model.key_of(record.id)

    return name


__all__ = ["EQUATION_COLUMNS", "Equation", "Equations"]
