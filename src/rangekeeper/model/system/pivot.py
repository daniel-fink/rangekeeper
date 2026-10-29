"""One recorded Value pivoted over a rows tree and a Taxonomy's columns.

The columns test each Entity's Classification or, with a label key, the
Classifications of its Label with that key.

Every cell is a ``RollupEntry`` from a rollup's ``execute``. A Pivot adds no
arithmetic; it only chooses each column's contributors and compares populations.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper.flow import Flow
from rangekeeper.model import Entity, Label
from rangekeeper.model.definitions import _classes
from rangekeeper.model.system.errors import RollupError
from rangekeeper.model.system.hierarchy import Hierarchy
from rangekeeper.model.system.rollup import (
    Contributor,
    Coverage,
    RollupEntry,
    RollupResult,
    _Decision,
)
from rangekeeper.quantity import Quantity
from rangekeeper.shared.arguments import require_text
from rangekeeper.shared.errors import MissingReferenceError

if TYPE_CHECKING:
    from rangekeeper.model.display import PivotTable
    from rangekeeper.model.system.rollup import _Rollup
    from rangekeeper.shared.table import Table


@dataclass(frozen=True, kw_only=True)
class PivotColumn:
    """One column: a Classification, its parent column and its RollupResult.

    ``classification=None`` is the "All" column, at depth 0. A ``parent`` of
    None means the "All" column is the parent.
    """

    classification: UUID | None
    parent: UUID | None
    depth: int
    result: RollupResult

    def __post_init__(self) -> None:
        for name in ("classification", "parent"):
            item = getattr(self, name)
            if item is not None and not isinstance(item, UUID):
                raise TypeError(f"{name} must be a UUID or None")
        if type(self.depth) is not int or self.depth < 0:
            raise TypeError("depth must be a non-negative int")
        if not isinstance(self.result, RollupResult):
            raise TypeError("result must be a RollupResult")
        if (self.classification is None) != (self.depth == 0):
            raise RollupError("only the All column has depth 0")
        if self.classification is None and self.parent is not None:
            raise RollupError("the All column has no parent")
        if self.parent is not None and self.parent == self.classification:
            raise RollupError("a column cannot be its own parent")


@dataclass(frozen=True, kw_only=True)
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
    """Columns of RollupResults over one rows Hierarchy, keyed by Classification.

    Columns keep their given order. Exactly one column is "All"
    (``classification=None``). Each column's parent is another column one level
    up. Every RollupResult must use ``rows``. ``label`` names the Label key whose
    Classifications chose the columns, or is None when the columns test each
    Entity's own Classification.
    """

    __slots__ = ("rows", "columns", "label", "_columns", "_children", "_positions")
    rows: Hierarchy
    columns: tuple[PivotColumn, ...]
    label: str | None
    _columns: Mapping[UUID | None, PivotColumn]
    _children: Mapping[UUID | None, tuple[PivotColumn, ...]]
    _positions: Mapping[UUID, int]

    def __init__(
        self,
        *,
        rows: Hierarchy,
        columns: Iterable[PivotColumn],
        label: str | None = None,
    ) -> None:
        if not isinstance(rows, Hierarchy):
            raise TypeError("rows must be a Hierarchy")
        if label is not None:
            require_text(label, "label")
        columns = tuple(columns)
        if any(not isinstance(item, PivotColumn) for item in columns):
            raise TypeError("columns must contain PivotColumn objects")
        index = {}
        for item in columns:
            if item.classification in index:
                raise RollupError("pivot columns must be unique")
            index[item.classification] = item
        if None not in index:
            raise RollupError("a pivot requires one All column")
        model = rows.view.model
        children: dict[UUID | None, list[PivotColumn]] = {}
        for item in columns:
            if item.result.hierarchy != rows:
                raise RollupError("every column must roll up the rows")
            if item.classification is None:
                continue
            model.classification(item.classification)
            parent = index.get(item.parent)
            if parent is None or item.depth != parent.depth + 1:
                raise RollupError(
                    f"column {item.classification} needs a parent column one level up"
                )
            children.setdefault(item.parent, []).append(item)
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "label", label)
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
        """Return a column by Classification UUID; None is the All column.

        A Classification without a column raises MissingReferenceError.
        """
        key = column.classification if isinstance(column, PivotColumn) else column
        if key is not None and not isinstance(key, UUID):
            raise TypeError("column must be a UUID, PivotColumn or None")
        found = self._columns.get(key)
        if found is None:
            raise MissingReferenceError(key, kind="PivotColumn", by="id", where="Pivot")
        return found

    def children(
        self,
        column: "UUID | PivotColumn | None" = None,
    ) -> tuple[PivotColumn, ...]:
        """Return the sub-columns of a column, in column order."""
        return self._children.get(self.column(column).classification, ())

    def cell(
        self,
        *,
        row: UUID,
        column: "UUID | PivotColumn | None" = None,
    ) -> RollupEntry:
        """Return the RollupEntry for a row and column."""
        self.rows.view.entity(row)
        return self.column(column).result.entries[row]

    def value(
        self,
        *,
        row: UUID,
        column: "UUID | PivotColumn | None" = None,
    ) -> Quantity | Flow | None:
        """Return the cell result under its column's coverage policy."""
        return self.column(column).result.value(row)

    def coverage(
        self,
        *,
        row: UUID,
        column: "UUID | PivotColumn | None" = None,
    ) -> Coverage:
        """Return the contributor coverage of one cell."""
        return self.column(column).result.coverage(row)

    def available_value(
        self,
        *,
        row: UUID,
        column: "UUID | PivotColumn | None" = None,
    ) -> Quantity | Flow | None:
        """Return the result over measured contributors, despite missing ones."""
        return self.column(column).result.available_value(row)

    def partition(
        self,
        *,
        row: UUID,
        column: "UUID | PivotColumn | None" = None,
    ) -> Partition:
        """Compare a column's records with its sub-columns' records at one row.

        A column without sub-columns has every record uncovered.
        """
        selected = set(self.coverage(row=row, column=column).selected)
        counts: dict[UUID, int] = {}
        for child in self.children(column):
            for id in child.result.coverage(row).selected:
                counts[id] = counts.get(id, 0) + 1

        def ordered(ids):
            return tuple(sorted(ids, key=self._positions.__getitem__))

        overlap = ordered(id for id, n in counts.items() if n > 1)
        uncovered = ordered(selected - set(counts))
        outside = ordered(set(counts) - selected)
        return Partition(
            complete=not (overlap or uncovered or outside),
            overlap=overlap,
            uncovered=uncovered,
            outside=outside,
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
            cells: dict[str, object] = {
                "name": entity.name,
                "parent_id": self.rows.parent(id),
            }
            for item, label in zip(self.columns, labels, strict=True):
                cells[label] = self.value(row=id, column=item)
            rows.append(Row(cells, id))
        return Table(("name", "parent_id", *labels), rows)

    def display(self, *, precision: int = 2) -> "PivotTable":
        """Return an HTML/text table of scalar cells, with rows indented by depth."""
        from rangekeeper.model.display import PivotTable

        return PivotTable(pivot=self, precision=precision)

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


def _base_rule(
    rollup: "_Rollup",
    rows: Hierarchy,
) -> Callable[[Entity], bool | None]:
    rule = rollup._contributor_rule(rows.view.model)
    if rule is Contributor.ALL:
        return lambda entity: True
    if rule is Contributor.LEAVES:
        return lambda entity: not rows.children(entity.id)
    if isinstance(rule, _Decision):
        return rule

    def checked(entity: Entity) -> bool:
        eligible = rule(entity)
        if type(eligible) is not bool:
            raise TypeError("contributors must return bool")
        return eligible

    return checked


def _member(model, label, classes):
    """Test an Entity's Classification, or its Label with key ``label``."""
    if label is None:
        return lambda entity: entity.classification in classes

    def labelled(entity: Entity) -> bool:
        found = model._local(Label, entity.id, label)
        return found is not None and any(
            item in classes for item in found.classifications or ()
        )

    return labelled


def _rule(base, tests):
    """Require the column tests, then the base rule, which may be undecided.

    An Entity outside the column is not a contributor of the column, even when
    the base rule cannot decide it.
    """
    return _Decision(
        lambda entity: all(test(entity) for test in tests) and base(entity)
    )


def _label_root(model, rows: Hierarchy, label: str) -> UUID | None:
    """Return the root of the one Taxonomy of the rows' ``label`` Labels."""
    owners = {}
    for taxonomy in (model.definitions.taxonomies if model.definitions else None) or ():
        for item in taxonomy.classifications:
            owners[item.id] = taxonomy
    found = {}
    for id in rows.preorder():
        record = model._local(Label, id, label)
        for item in (record.classifications if record else None) or ():
            taxonomy = owners[item]
            found[taxonomy.id] = taxonomy
    if len(found) > 1:
        raise RollupError(
            f"Labels {label!r} use Classifications of several Taxonomies; "
            "pass by= to choose the column parent"
        )
    if not found:
        return None
    (taxonomy,) = found.values()
    return next(item.id for item in taxonomy.classifications if item.parent is None)


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
    rollup: "_Rollup",
    hierarchy: Hierarchy,
    *,
    by: UUID | None = None,
    depth: int = 1,
    only: UUID | None = None,
    exclusive: bool = False,
    label: str | None = None,
) -> Pivot:
    """Run one rollup per column; see ``QuantityRollup.pivot``."""
    if not isinstance(hierarchy, Hierarchy):
        raise TypeError("hierarchy must be a Hierarchy")
    if type(depth) is not int:
        raise TypeError("depth must be an int")
    if depth < 1:
        raise RollupError("depth must be at least 1")
    if type(exclusive) is not bool:
        raise TypeError("exclusive must be bool")
    if label is not None:
        require_text(label, "label")
    model = hierarchy.view.model
    definitions = model.definitions
    if by is None and label is not None:
        by = _label_root(model, hierarchy, label)
    base = _base_rule(rollup, hierarchy)
    scope = (
        ()
        if only is None
        else (_member(model, None, _classes(definitions, only, exclusive=exclusive)),)
    )
    everything = (
        rollup.execute(hierarchy)
        if only is None
        else replace(rollup, contributors=_rule(base, scope)).execute(hierarchy)
    )
    columns = [
        PivotColumn(classification=None, parent=None, depth=0, result=everything)
    ]
    if by is not None:
        model.classification(by)
        for id, parent, level in _column_classes(definitions, by, depth):
            classes = _classes(definitions, id, exclusive=exclusive)
            rule = _rule(base, (*scope, _member(model, label, classes)))
            columns.append(
                PivotColumn(
                    classification=id,
                    parent=parent,
                    depth=level,
                    result=replace(rollup, contributors=rule).execute(hierarchy),
                )
            )
    return Pivot(rows=hierarchy, columns=columns, label=label)


__all__ = ["Pivot", "PivotColumn", "Partition"]
