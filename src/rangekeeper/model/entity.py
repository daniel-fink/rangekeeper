"""The entities of one Model revision, with their values and the units of each.

``model.entity(code=)`` returns a ``ModelEntity``: a read-only view of one Entity
or Assembly of the revision. ``record`` is the generated record. ``values`` is a
Table with one row for each Value, which shows its units and whether the draft
declared or inferred them (D44).
"""

from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper.schema.records import Assembly, Entity, Measure, Value
from rangekeeper.shared.table import Row, Table

if TYPE_CHECKING:
    # The Model makes its entities and imports this module.
    from rangekeeper.model.model import Model

# The columns of ``ModelEntity.values``.
VALUE_COLUMNS = ("key", "kind", "units", "inferred", "description")


class ModelEntity:
    """An Entity or Assembly of one Model revision, with its values and their units.

    ``model.entity(...)`` returns one; only a Model makes one. ``record`` is the
    generated Entity or Assembly record, and ``id``, ``code``, ``name`` and
    ``classification`` are its fields. Two entities are equal when they are
    the same record of the same revision. The display names the kind, code and
    name, for example ``<entity project 'Project'>``.
    """

    __slots__ = ("_model", "_record")
    _model: "Model"
    _record: Entity

    def __init__(self) -> None:
        raise TypeError("a Model makes ModelEntities; call model.entity()")

    @classmethod
    def _of(cls, model: "Model", record: Entity) -> "ModelEntity":
        """Return the view of ``record``, an Entity or Assembly of ``model``."""
        entity = cls.__new__(cls)
        entity._model = model
        entity._record = record
        return entity

    @property
    def record(self) -> Entity:
        """The generated Entity or Assembly record."""
        return self._record

    @property
    def id(self) -> UUID:
        """The UUID of the Entity or Assembly."""
        return self._record.id

    @property
    def code(self) -> str | None:
        """The code of the Entity or Assembly, or None."""
        return self._record.code

    @property
    def name(self) -> str | None:
        """The name of the Entity or Assembly, or None."""
        return self._record.name

    @property
    def classification(self) -> UUID | None:
        """The UUID of the Classification of the Entity or Assembly, or None."""
        return self._record.classification

    @property
    def values(self) -> Table:
        """A Table with one row for each Value of the entity, in declaration order.

        The columns are ``key``, ``kind`` (a ``ValueKind``), ``units`` (the
        units of its Measure, or None for a date or a property), ``inferred``
        (True when the draft worked out the kind and units from the equations,
        False when a call declared them) and ``description``. Each row's id is
        the UUID of the Value.
        """
        characteristics = self._record.characteristics
        values = () if characteristics is None else characteristics.values or ()
        return Table(VALUE_COLUMNS, [self._row(value) for value in values])

    def _row(self, value: Value) -> Row:
        measure = None
        if value.measure is not None:
            measure = self._model._index.get(value.measure, Measure)
        return Row(
            {
                "key": value.key,
                "kind": value.kind,
                "units": None if measure is None else measure.units,
                "inferred": bool(value.inferred),
                "description": value.description,
            },
            id=value.id,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModelEntity):
            return NotImplemented
        return self._model.id == other._model.id and self._record == other._record

    def __hash__(self) -> int:
        return hash((self._model.id, self._record.id))

    def __repr__(self) -> str:
        word = "assembly" if isinstance(self._record, Assembly) else "entity"
        name = "" if self.name is None else f" {self.name!r}"
        return f"<{word} {self.code or self.id}{name}>"


__all__ = ["ModelEntity", "VALUE_COLUMNS"]
