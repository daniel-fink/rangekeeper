"""Explicit, read-only projections of a pinned Model into domain-independent Tables."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, unique
from uuid import UUID

from ..model import Assembly, Classification, Measure, ValueKind
from ..model.characteristics import label, value
from ..model.content import decode
from ..table import Row, Table, TableError, _validate_names
from ..units import UnitSystem, default_units
from ..validate import require_text
from .hierarchy import Hierarchy
from .selection import _local_value, select_value
from .view import View


@unique
class EntityField(Enum):
    MODEL_ID = "model_id"
    ENTITY_ID = "entity_id"
    CODE = "code"
    NAME = "name"
    ENTITY_KIND = "entity_kind"
    CLASSIFICATION_ID = "classification_id"
    CLASSIFICATION_CODE = "classification_code"
    CLASSIFICATION_NAME = "classification_name"


@dataclass(frozen=True, slots=True)
class FieldColumn:
    """A named column containing a public Entity field or its pinned revision UUID."""

    name: str
    field: EntityField

    def __post_init__(self):
        require_text(self.name, "column name")
        if not isinstance(self.field, EntityField):
            raise TypeError("field must be EntityField")


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
    FieldColumn("model_id", EntityField.MODEL_ID),
    FieldColumn("entity_id", EntityField.ENTITY_ID),
    FieldColumn("name", EntityField.NAME),
)


def to_table(
    source: View | Hierarchy,
    *,
    columns: Iterable[Column] = DEFAULT_COLUMNS,
    units: UnitSystem = default_units,
) -> Table:
    """Return selected canonical Entities once, in View order, without I/O.

    Row identity is the Entity UUID. Include model_id when rows leave the pinned
    View context. Columns are explicit, unique names; unsupported column objects
    raise TypeError. A Table is a projection and cannot reload a Model.
    """
    if not isinstance(source, (View, Hierarchy)):
        raise TypeError("source must be a Model-backed View or Hierarchy")
    if isinstance(source, Hierarchy):
        hierarchy, view = source, source.view
    else:
        hierarchy, view = None, source
    columns = tuple(columns)
    if any(
        not isinstance(c, (FieldColumn, ValueColumn, LabelColumn, PropertyColumn))
        for c in columns
    ):
        raise TypeError(
            "columns must contain FieldColumn, ValueColumn, LabelColumn or PropertyColumn"
        )
    names = _validate_names((c.name for c in columns), "columns")
    if hierarchy is not None and "parent_id" in names:
        raise TableError("parent_id is reserved for the tree projection")
    # Validate requested units even for an empty View or wholly missing column.
    for c in columns:
        if isinstance(c, ValueColumn):
            units.validate_units(c.units)
            if c.measure is not None:
                view.model._index.get(c.measure, Measure)
    rows = []
    entities = (
        view.entities
        if hierarchy is None
        else (view.entity(uid) for uid in hierarchy.preorder())
    )
    for entity in entities:
        cells = {}
        for c in columns:
            result: object
            if isinstance(c, ValueColumn):
                item = _local_value(entity, c.key, c.measure)
                result = (
                    None
                    if item is None or item.quantity is None
                    else units.convert(item.quantity, to=c.units).magnitude
                )
            elif isinstance(c, PropertyColumn):
                item = value(entity.characteristics, c.key)
                if item is not None and item.kind is not ValueKind.PROPERTY:
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
            elif c.field is EntityField.MODEL_ID:
                result = view.model.id
            elif c.field is EntityField.ENTITY_ID:
                result = entity.id
            elif c.field is EntityField.ENTITY_KIND:
                result = "assembly" if isinstance(entity, Assembly) else "entity"
            elif c.field is EntityField.CLASSIFICATION_ID:
                result = entity.classification
            elif c.field.value.startswith("classification_"):
                kind = (
                    view.model._index.get(entity.classification, Classification)
                    if entity.classification
                    else None
                )
                result = (
                    getattr(kind, c.field.value.removeprefix("classification_"))
                    if kind
                    else None
                )
            else:
                result = getattr(entity, c.field.value)
            cells[c.name] = result
        if hierarchy is not None:
            cells["parent_id"] = hierarchy.parent(entity.id)
        rows.append(Row(cells, entity.id))
    return Table(names if hierarchy is None else (*names, "parent_id"), rows)


__all__ = [
    "EntityField",
    "FieldColumn",
    "ValueColumn",
    "LabelColumn",
    "PropertyColumn",
    "Column",
    "to_table",
]
