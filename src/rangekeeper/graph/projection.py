"""Explicit, read-only projections of a pinned Model into domain-independent Tables."""

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from ..model import Assembly
from ..model.characteristics import label, value
from ..model.content import decode
from ..model.definitions import classification, measure as find_measure
from ..table import Row, Table, TableError
from ..units import UnitSystem, default_units
from ..validate import require_text
from .hierarchy import Hierarchy
from .selection import select_value
from .view import View

_FIELDS = frozenset(
    {
        "model_id",
        "entity_id",
        "code",
        "name",
        "entity_kind",
        "classification_id",
        "classification_code",
        "classification_name",
    }
)


@dataclass(frozen=True, slots=True)
class FieldColumn:
    """A named column containing a public Entity field or its pinned revision UUID."""

    name: str
    field: str

    def __post_init__(self):
        require_text(self.name, "column name")
        if self.field not in _FIELDS:
            raise TableError(f"unknown Entity field: {self.field}")


@dataclass(frozen=True, slots=True)
class ValueColumn:
    """Project one owner-local Value to explicit units; absent/unresolved gives None.

    A zero remains zero. Selecting the wrong Measure or incompatible units raises;
    a Measure alone never selects a Value. Use Model access for Value provenance.
    """

    name: str
    key: str
    units: str
    measure: UUID | None = None

    def __post_init__(self):
        require_text(self.name, "column name")
        require_text(self.units, "units")
        select_value(self.key, measure=self.measure)


@dataclass(frozen=True, slots=True)
class LabelColumn:
    """Project one local Label to classification UUIDs; missing gives None."""

    name: str
    key: str

    def __post_init__(self):
        require_text(self.name, "column name")
        require_text(self.key, "key")


@dataclass(frozen=True, slots=True)
class PropertyColumn:
    """Detached rich property content selected by owner-local key.

    Missing or explicit null returns None; false and zero retain their types.
    A non-property Value raises TableError. No Model internals are exposed.
    """

    name: str
    key: str

    def __post_init__(self):
        require_text(self.name, "column name")
        require_text(self.key, "key")


Column = FieldColumn | ValueColumn | LabelColumn | PropertyColumn
DEFAULT_COLUMNS = (
    FieldColumn("model_id", "model_id"),
    FieldColumn("entity_id", "entity_id"),
    FieldColumn("name", "name"),
)


def to_table(
    view: View,
    *,
    columns: Iterable[Column] = DEFAULT_COLUMNS,
    units: UnitSystem = default_units,
) -> Table:
    """Return selected canonical Entities once, in View order, without I/O.

    Row identity is the Entity UUID. Include model_id when rows leave the pinned
    View context. Columns are explicit, unique names; unsupported column objects
    raise TypeError. A Table is a projection and cannot reload a Model.
    """
    if not isinstance(view, View):
        raise TypeError("view must be a Model-backed View")
    columns = tuple(columns)
    if any(
        not isinstance(c, (FieldColumn, ValueColumn, LabelColumn, PropertyColumn))
        for c in columns
    ):
        raise TypeError("columns must contain FieldColumn, ValueColumn or LabelColumn")
    names = Table((c.name for c in columns), ()).columns
    # Validate requested units even for an empty View or wholly missing column.
    for c in columns:
        if isinstance(c, ValueColumn):
            units.compatible(c.units, c.units)
            if c.measure is not None:
                find_measure(view.model.definitions, c.measure)
    rows = []
    for entity in view.entities:
        cells = {}
        for c in columns:
            result: object
            if isinstance(c, ValueColumn):
                item = select_value(c.key, measure=c.measure)(view.model, entity)
                result = (
                    None
                    if item is None or item.quantity is None
                    else units.convert(item.quantity, to=c.units).magnitude
                )
            elif isinstance(c, PropertyColumn):
                item = value(entity.characteristics, c.key)
                if item is not None and item.kind != "property":
                    raise TableError(f"{c.key} is not a property Value")
                result = (
                    decode(item.content)
                    if item is not None and item.content is not None
                    else None
                )
            elif isinstance(c, LabelColumn):
                selected_label = label(entity.characteristics, c.key)
                result = (
                    None if selected_label is None else selected_label.classifications
                )
            elif c.field == "model_id":
                result = view.model.id
            elif c.field == "entity_id":
                result = entity.id
            elif c.field == "entity_kind":
                result = "assembly" if isinstance(entity, Assembly) else "entity"
            elif c.field == "classification_id":
                result = entity.classification
            elif c.field.startswith("classification_"):
                kind = (
                    classification(view.model.definitions, entity.classification)
                    if entity.classification
                    else None
                )
                result = (
                    getattr(kind, c.field.removeprefix("classification_"))
                    if kind
                    else None
                )
            else:
                result = getattr(entity, c.field)
            cells[c.name] = result
        rows.append(Row(cells, entity.id))
    return Table(names, rows)


def to_tree_table(
    hierarchy: Hierarchy,
    *,
    columns: Iterable[Column] = DEFAULT_COLUMNS,
    units: UnitSystem = default_units,
) -> Table:
    """Return preorder rows with explicit parent_id from a validated Hierarchy.

    Both relationship and membership trees are supported. Overlapping membership
    needs an occurrence-based viewer, not this one-row-per-Entity tree format.
    """
    if not isinstance(hierarchy, Hierarchy):
        raise TypeError("hierarchy must be a Hierarchy")
    table = to_table(hierarchy.view, columns=columns, units=units)
    if "parent_id" in table.columns:
        raise TableError("parent_id is reserved for the tree projection")
    return Table(
        (*table.columns, "parent_id"),
        (
            Row({**table.row(uid).values, "parent_id": hierarchy.parent(uid)}, uid)
            for uid in hierarchy.preorder()
        ),
    )


__all__ = [
    "FieldColumn",
    "ValueColumn",
    "LabelColumn",
    "PropertyColumn",
    "Column",
    "to_table",
    "to_tree_table",
]
