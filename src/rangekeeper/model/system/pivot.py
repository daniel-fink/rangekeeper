"""One recorded Value pivoted over a rows tree and a Taxonomy's columns.

Every cell is an ``AggregateEntry`` from ``Reduction.execute``. A Pivot adds no
arithmetic; it only chooses each column's contributors and compares populations.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper.model import Entity
from rangekeeper.schema.records import Flow, Quantity
from rangekeeper.model.definitions import _classes
from rangekeeper.model.system.errors import AggregationError
from rangekeeper.model.system.hierarchy import Hierarchy
from rangekeeper.model.system.reduction import (
    AggregateEntry,
    Aggregation,
    Contributor,
    Coverage,
)

if TYPE_CHECKING:
    from rangekeeper.model.system.reduction import Reduction
    from rangekeeper.shared.table import Table


@dataclass(frozen=True)
class PivotColumn:
    """One column: a Classification, its parent column and its Aggregation.

    ``classification=None`` is the "All" column, at depth 0. A ``parent`` of
    None means the "All" column is the parent.
    """

    classification: UUID | None
    parent: UUID | None
    depth: int
    aggregation: Aggregation

    def __post_init__(self) -> None:
        for name in ("classification", "parent"):
            item = getattr(self, name)
            if item is not None and not isinstance(item, UUID):
                raise TypeError(f"{name} must be a UUID or None")
        if type(self.depth) is not int or self.depth < 0:
            raise TypeError("depth must be a non-negative int")
        if not isinstance(self.aggregation, Aggregation):
            raise TypeError("aggregation must be an Aggregation")
        if (self.classification is None) != (self.depth == 0):
            raise AggregationError("only the All column has depth 0")
        if self.classification is None and self.parent is not None:
            raise AggregationError("the All column has no parent")
        if self.parent is not None and self.parent == self.classification:
            raise AggregationError("a column cannot be its own parent")


@dataclass(frozen=True)
class Partition:
    """Whether a column's sub-columns hold exactly its records, once each.

    The sets compare ``Coverage.selected``, not values. ``overlap`` holds records
    in more than one sub-column. ``uncovered`` holds records of the column in no
    sub-column. ``outside`` holds sub-column records that the column does not
    select. A complete partition of a sum means the sub-column sums add up.
    """

    complete: bool
    overlap: tuple[UUID, ...]
    uncovered: tuple[UUID, ...]
    outside: tuple[UUID, ...]


@dataclass(frozen=True, init=False)
class Pivot:
    """Columns of Aggregations over one rows Hierarchy, keyed by Classification.

    Columns keep their given order. Exactly one column is "All"
    (``classification=None``). Each column's parent is another column one level
    up. Every Aggregation must use ``rows``.
    """

    __slots__ = ("rows", "columns", "_columns", "_children", "_positions")
    rows: Hierarchy
    columns: tuple[PivotColumn, ...]

    def __init__(self, rows: Hierarchy, columns: Iterable[PivotColumn]) -> None:
        if not isinstance(rows, Hierarchy):
            raise TypeError("rows must be a Hierarchy")
        columns = tuple(columns)
        if any(not isinstance(item, PivotColumn) for item in columns):
            raise TypeError("columns must contain PivotColumn objects")
        index = {}
        for item in columns:
            if item.classification in index:
                raise AggregationError("pivot columns must be unique")
            index[item.classification] = item
        if None not in index:
            raise AggregationError("a pivot requires one All column")
        model = rows.view.model
        children: dict[UUID | None, list[PivotColumn]] = {}
        for item in columns:
            if item.aggregation.hierarchy != rows:
                raise AggregationError("every column must aggregate the rows")
            if item.classification is None:
                continue
            model.classification(item.classification)
            parent = index.get(item.parent)
            if parent is None or item.depth != parent.depth + 1:
                raise AggregationError(
                    f"column {item.classification} needs a parent column one level up"
                )
            children.setdefault(item.parent, []).append(item)
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "_columns", MappingProxyType(index))
        object.__setattr__(
            self,
            "_children",
            MappingProxyType({key: tuple(value) for key, value in children.items()}),
        )
        object.__setattr__(
            self,
            "_positions",
            MappingProxyType({id: n for n, id in enumerate(rows.preorder())}),
        )

    def column(self, column: "UUID | PivotColumn | None" = None) -> PivotColumn:
        """Return a column by Classification UUID; None is the All column."""
        key = column.classification if isinstance(column, PivotColumn) else column
        if key is not None and not isinstance(key, UUID):
            raise TypeError("column must be a UUID, PivotColumn or None")
        try:
            return self._columns[key]
        except KeyError:
            raise KeyError(f"no pivot column for {key}") from None

    def children(self, column: "UUID | PivotColumn | None" = None):
        """Return the sub-columns of a column, in column order."""
        return self._children.get(self.column(column).classification, ())

    def cell(
        self, row: UUID, column: "UUID | PivotColumn | None" = None
    ) -> AggregateEntry:
        """Return the AggregateEntry for a row and column."""
        self.rows.view.entity(row)
        return self.column(column).aggregation.entries[row]

    def value(
        self, row: UUID, column: "UUID | PivotColumn | None" = None
    ) -> Quantity | Flow | None:
        """Return the cell result under its column's coverage policy."""
        return self.column(column).aggregation.value(row)

    def coverage(
        self, row: UUID, column: "UUID | PivotColumn | None" = None
    ) -> Coverage:
        return self.column(column).aggregation.coverage(row)

    def available_value(
        self, row: UUID, column: "UUID | PivotColumn | None" = None
    ) -> Quantity | Flow | None:
        """Return the reduction over measured contributors, despite missing ones."""
        return self.column(column).aggregation.available_value(row)

    def partition(
        self, row: UUID, column: "UUID | PivotColumn | None" = None
    ) -> Partition:
        """Compare a column's records with its sub-columns' records at one row.

        A column without sub-columns has every record uncovered.
        """
        selected = set(self.coverage(row, column).selected)
        counts: dict[UUID, int] = {}
        for child in self.children(column):
            for id in child.aggregation.coverage(row).selected:
                counts[id] = counts.get(id, 0) + 1

        def ordered(ids):
            return tuple(sorted(ids, key=self._positions.__getitem__))

        overlap = ordered(id for id, n in counts.items() if n > 1)
        uncovered = ordered(selected - set(counts))
        outside = ordered(set(counts) - selected)
        return Partition(
            not (overlap or uncovered or outside), overlap, uncovered, outside
        )

    def to_table(self) -> "Table":
        """Return rows in preorder with one cell per column, for inspection.

        Columns are ``name``, ``parent_id``, ``All`` and each Classification code.
        Cells hold ``value`` results: a Quantity, a Flow or None. Row IDs are
        Entity UUIDs. A Classification code that repeats a column name raises
        ``TableError``.
        """
        from rangekeeper.shared.table import Row, Table

        labels = self._labels()
        rows = []
        for id in self.rows.preorder():
            entity = self.rows.view.entity(id)
            cells = {"name": entity.name, "parent_id": self.rows.parent(id)}
            for item, label in zip(self.columns, labels):
                cells[label] = self.value(id, item)
            rows.append(Row(cells, id))
        return Table(("name", "parent_id", *labels), rows)

    def display(self, *, precision: int = 2):
        """Return an HTML/text table of scalar cells, with rows indented by depth."""
        from rangekeeper.visualisation.table import PivotTable

        return PivotTable(self, precision=precision)

    def _labels(self) -> tuple[str, ...]:
        model = self.rows.view.model
        return tuple(
            (
                "All"
                if item.classification is None
                else model.classification(item.classification).code
            )
            for item in self.columns
        )


def _base_rule(reduction: "Reduction", rows: Hierarchy) -> Callable[[Entity], bool]:
    rule = reduction.contributors
    if rule is None or rule is Contributor.ALL:
        return lambda entity: True
    if rule is Contributor.LEAVES:
        return lambda entity: not rows.children(entity.id)

    def checked(entity: Entity) -> bool:
        eligible = rule(entity)
        if type(eligible) is not bool:
            raise TypeError("contributors must return bool")
        return eligible

    return checked


def _rule(base, classes):
    if not classes:
        return base
    return lambda entity: base(entity) and all(
        entity.classification in group for group in classes
    )


def _column_classes(definitions, by, depth):
    """Return (classification, parent, depth) below ``by`` in Taxonomy preorder."""
    for taxonomy in definitions.taxonomies or ():
        records = taxonomy.classifications
        if not any(item.id == by for item in records):
            continue
        children: dict[UUID, list[UUID]] = {}
        for item in records:
            if item.parent is not None:
                children.setdefault(item.parent, []).append(item.id)
        found = []
        pending = [(id, None, 1) for id in reversed(children.get(by, ()))]
        while pending:
            id, parent, level = pending.pop()
            found.append((id, parent, level))
            if level < depth:
                pending.extend(
                    (child, id, level + 1) for child in reversed(children.get(id, ()))
                )
        return found
    return []


def pivot(
    reduction: "Reduction",
    hierarchy: Hierarchy,
    *,
    by: UUID | None = None,
    depth: int = 1,
    only: UUID | None = None,
    exclusive: bool = False,
) -> Pivot:
    """Run one Reduction per column; see ``Reduction.pivot``."""
    if not isinstance(hierarchy, Hierarchy):
        raise TypeError("hierarchy must be a Hierarchy")
    if type(depth) is not int or depth < 1:
        raise ValueError("depth must be a positive int")
    if type(exclusive) is not bool:
        raise TypeError("exclusive must be bool")
    model = hierarchy.view.model
    definitions = model.definitions
    base = _base_rule(reduction, hierarchy)
    scope = () if only is None else (_classes(definitions, only, exclusive=exclusive),)
    everything = (
        reduction.execute(hierarchy)
        if only is None
        else replace(reduction, contributors=_rule(base, scope)).execute(hierarchy)
    )
    columns = [PivotColumn(None, None, 0, everything)]
    if by is not None:
        model.classification(by)
        for id, parent, level in _column_classes(definitions, by, depth):
            rule = _rule(base, (*scope, _classes(definitions, id, exclusive=exclusive)))
            columns.append(
                PivotColumn(
                    id,
                    parent,
                    level,
                    replace(reduction, contributors=rule).execute(hierarchy),
                )
            )
    return Pivot(hierarchy, columns)


__all__ = ["Pivot", "PivotColumn", "Partition"]
