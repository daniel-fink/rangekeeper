"""One self-contained, immutable Model revision and its derived lookup indexes."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

from rangekeeper.model.update import Update
from rangekeeper.schema.index import RecordIndex, RecordLocation, record_at
from rangekeeper.schema.records import (
    Assembly,
    Claim,
    Classification,
    Definitions,
    Entity,
    Formulation,
    Geometry,
    Metadata,
    Movement,
    Provenance,
    Reference,
    Relationship,
    Source,
    System,
    Value,
)
from rangekeeper.schema.records import (
    Model as ModelRecord,
)
from rangekeeper.schema.revision import check_revision
from rangekeeper.schema.runtime import UNSET, Record, Unset
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.arguments import optional_text, require_uuid
from rangekeeper.shared.errors import UnsupportedVersionError
from rangekeeper.shared.units import UnitSystem, default_units


@dataclass(frozen=True, init=False, eq=False)
class Model:
    """A validated revision, with no store, solver, or predecessor lookup.

    The generated record owns fields. This facade adds scoped lookup and revision
    behavior; callers receive immutable generated records rather than live objects
    that can mutate a shared graph. Construct via ``create`` or ``from_data``.
    """

    # Manual slots avoid Python 3.10's frozen-dataclass/property assignment bug.
    __slots__ = (
        "_record",
        "_index",
        "_units",
    )
    _record: ModelRecord
    _index: RecordIndex
    _units: UnitSystem

    def __init__(
        self,
        record: ModelRecord,
        *,
        units: UnitSystem = default_units,
    ) -> None:
        if not isinstance(record, ModelRecord):
            raise TypeError("record must be a generated Model record")
        if not isinstance(units, UnitSystem):
            raise TypeError("units must be a UnitSystem")
        if record.metadata.schema_version not in ("0.7.0", document_version("Model")):
            raise UnsupportedVersionError(record.metadata.schema_version)
        index = RecordIndex.build(record)
        from rangekeeper.model.validation import _validate

        _validate(record, index=index, units=units).raise_if_invalid()
        # Publish state only after both structural/local indexes and semantics pass.
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "_index", index)
        object.__setattr__(self, "_units", units)

    @classmethod
    def from_data(
        cls,
        data: Mapping[str, object],
        *,
        units: UnitSystem = default_units,
    ) -> "Model":
        """Copy, structurally and semantically validate, then freeze one revision.

        Invalid structure/semantics raises ValidationError; unsupported versions and
        duplicate identities have distinct errors. No history or filesystem is read.
        """
        return cls(ModelRecord.from_data(data), units=units)

    @classmethod
    def create(
        cls,
        *,
        metadata: Metadata,
        definitions: Definitions | Unset = UNSET,
        system: System | Unset = UNSET,
        provenance: Provenance | Unset = UNSET,
        geometry: Geometry | Unset = UNSET,
        units: UnitSystem = default_units,
    ) -> "Model":
        """Build a complete Model from typed sections through the same validation path."""
        return cls(
            ModelRecord(
                metadata=metadata,
                definitions=definitions,
                system=system,
                provenance=provenance,
                geometry=geometry,
            ),
            units=units,
        )

    @property
    def id(self) -> UUID:
        """The revision UUID, forwarded from Metadata; not a second identity."""
        return self.metadata.id

    @property
    def unit_system(self) -> UnitSystem:
        """The unit system that validated this revision; derived operations use it by default.

        A revision keeps the unit system of its predecessor.
        """
        return self._units

    @property
    def metadata(self) -> Metadata:
        """Immutable revision identity, lineage and description."""
        return self._record.metadata

    @property
    def definitions(self) -> Definitions | None:
        """Declared catalogues, or None when the section was omitted."""
        return self._record.definitions

    @property
    def system(self) -> System | None:
        """Canonical domain and mathematics, with Assemblies stored separately."""
        return self._record.system

    @property
    def provenance(self) -> Provenance | None:
        """Recorded evidence; opaque Claim content is never indexed as declarations."""
        return self._record.provenance

    @property
    def geometry(self) -> Geometry | None:
        """Optional exact native dataset and Model-owned Entity associations."""
        return self._record.geometry

    def to_data(self) -> dict[str, object]:
        """Export detached data, preserving presence and original collection order."""
        return self._record.to_data()

    def record_at(self, path: str) -> RecordLocation:
        """Locate one embedded record by its original canonical JSON pointer.

        The empty path selects the root. Scalar, absent and opaque locations raise
        MissingReferenceError. Malformed pointers and index aliases raise ValueError;
        a non-string raises TypeError. No references or history are followed.
        """
        return record_at(self._record, path)

    def record_by_id(self, id: UUID) -> RecordLocation:
        """Locate one declaration in this revision with constant index lookup.

        Require an actual UUID and raise MissingReferenceError when it is absent.
        The revision UUID selects Metadata, not the anonymous Model root.
        """
        record = self._index.get(id, Record)
        return RecordLocation(record, self._index.owners[id], self._index.paths[id])

    def __repr__(self) -> str:
        return f"Model(id={self.id!r}, declarations={len(self._index.records) - 1})"

    def classification(self, id: UUID) -> Classification:
        """Resolve a Classification in this exact Model revision."""
        return self._index.get(id, Classification)

    def descendants(self, classification: UUID) -> tuple[Classification, ...]:
        """Return the sub-types of a Classification in its Taxonomy, at any depth.

        The result is in declaration order and excludes the Classification itself.
        """
        from rangekeeper.model.definitions import _descendants

        self.classification(classification)
        return _descendants(self.definitions, classification)

    def entity(self, id: UUID) -> Entity:
        """Resolve an Entity or canonical Assembly; no code/name or history fallback."""
        return self._index.get(id, Entity)

    def assembly(self, id: UUID) -> Assembly:
        """Resolve an Assembly; an ordinary Entity has the wrong record kind."""
        return self._index.get(id, Assembly)

    def relationship(self, id: UUID) -> Relationship:
        """Resolve a Relationship in this revision; wrong kind and missing differ."""
        return self._index.get(id, Relationship)

    def value(self, id: UUID) -> Value:
        """Resolve a domain-owned or Formulation-local Value, including unresolved ones."""
        return self._index.get(id, Value)

    def movement(self, id: UUID) -> Movement:
        """Resolve one Movement by identity, independently of matching keys."""
        return self._index.get(id, Movement)

    def resolve(self, reference: Reference) -> Value | Movement:
        """Resolve a reference only in this complete Model revision."""
        if not isinstance(reference, Reference):
            raise TypeError("reference must be a Reference")
        record = self._index.get(reference.target, Record)
        if not isinstance(record, (Value, Movement)):
            raise TypeError("reference must target a Value or Movement")
        return record

    def formulation(self, id: UUID) -> Formulation:
        """Resolve a root or nested Formulation without flattening its ownership."""
        return self._index.get(id, Formulation)

    def claim(self, id: UUID) -> Claim:
        """Resolve evidence in this pinned revision; never load an external source."""
        return self._index.get(id, Claim)

    def source(self, id: UUID) -> Source:
        """Resolve recorded source metadata without opening its file or service."""
        return self._index.get(id, Source)

    def owner_of(self, id: UUID) -> UUID | None:
        """Return the nearest identified container, or None for anonymous root ownership."""
        self._index.get(id, Record)
        return self._index.owners[id]

    def find_entities(
        self,
        *,
        code: str | None = None,
        name: str | None = None,
        classification: UUID | None = None,
    ) -> tuple[Entity, ...]:
        """AND exact selectors in encounter order, including separately stored Assemblies.

        Classification descendants are not implicitly included; use ``descendants``
        or ``View.filter`` to include sub-types. Empty results are
        valid; unlike UUID lookup this is a search and never selects a unique result.
        """
        optional_text(code, "code")
        optional_text(name, "name")
        if classification is not None:
            require_uuid(classification, "classification")
        return tuple(
            record
            for record in self._index.records.values()
            if isinstance(record, Entity)
            and (code is None or record.code == code)
            and (name is None or record.name == name)
            and (classification is None or record.classification == classification)
        )

    def revise(self, update: Update) -> "Model":
        """Validate a complete candidate atomically and return a new revision.

        Omitted sections and provenance are preserved. Dangling references fail; no
        cascading repair occurs. A fresh UUID alone is not a meaningful update.
        """
        if not isinstance(update, Update):
            raise TypeError("update must be an Update")
        metadata = (
            self.metadata.replace(id=uuid4(), previous=self.id)
            if isinstance(update.metadata, Unset)
            else update.metadata
        )
        candidate = self._record.replace(
            metadata=metadata,
            definitions=update.definitions,
            system=update.system,
            provenance=update.provenance,
            geometry=update.geometry,
        )
        check_revision(self._record, candidate)
        return type(self)(candidate, units=self._units)
