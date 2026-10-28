"""One self-contained, immutable Model revision and its derived lookup indexes."""

from collections.abc import Mapping
from dataclasses import dataclass
from difflib import get_close_matches
from types import MappingProxyType
from typing import TypeVar, cast
from uuid import UUID, uuid4

from rangekeeper.flow import Movement
from rangekeeper.model.update import SECTIONS, Update
from rangekeeper.quantity import UnitSystem, default_units
from rangekeeper.schema.index import RecordIndex, RecordLocation, record_at
from rangekeeper.schema.records import (
    Assembly,
    Claim,
    Classification,
    Definitions,
    Entity,
    Formulation,
    Geometry,
    Label,
    Metadata,
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
from rangekeeper.schema.validation import document_version, supports_version
from rangekeeper.shared.arguments import optional_text, require_text, require_uuid
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    MissingReferenceError,
    UnsupportedVersionError,
)

K = TypeVar("K", Value, Label)


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
        "_keys",
        "_units",
    )
    _record: ModelRecord
    _index: RecordIndex
    # The UUID of each Value and Label by its kind, owner UUID and key.
    _keys: Mapping[tuple[type, UUID | None, str], UUID]
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
        if not supports_version(
            record.metadata.schema_version, document_version("Model")
        ):
            raise UnsupportedVersionError(record.metadata.schema_version)
        index = RecordIndex.build(record)
        from rangekeeper.model.validation import _validate

        _validate(record, index=index, units=units).raise_if_invalid()
        # Validation checks that keys are unique within each owner's collection.
        keys = {
            (type(item), index.owners[identity], item.key): identity
            for identity, item in index.records.items()
            if isinstance(item, (Value, Label))
        }
        # Publish state only after both structural/local indexes and semantics pass.
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "_index", index)
        object.__setattr__(self, "_keys", MappingProxyType(keys))
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

    def entity(
        self,
        id: UUID | None = None,
        *,
        code: str | None = None,
        name: str | None = None,
    ) -> Entity:
        """Return the one Entity or canonical Assembly with this UUID, code or name.

        Give exactly one selector. No match raises MissingReferenceError with the
        nearest codes or names; several matches raise AmbiguousReferenceError with
        their codes. ``find_entities`` is the search that can return none or several.
        """
        if sum(value is not None for value in (id, code, name)) != 1:
            raise TypeError("entity takes exactly one of id, code or name")
        if id is not None:
            return self._index.get(id, Entity)
        by, text = ("code", code) if code is not None else ("name", name)
        text = require_text(text, by)
        entities = [
            record
            for record in self._index.records.values()
            if isinstance(record, Entity)
        ]
        matches = [record for record in entities if getattr(record, by) == text]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise AmbiguousReferenceError(
                text,
                kind="Entity",
                by=by,
                where=self._index.where,
                candidates=[record.code or str(record.id) for record in matches],
            )
        names = {getattr(record, by) for record in entities} - {None}
        raise MissingReferenceError(
            text,
            kind="Entity",
            by=by,
            where=self._index.where,
            candidates=get_close_matches(text, sorted(names), n=3),
        )

    def assembly(self, id: UUID) -> Assembly:
        """Resolve an Assembly; an ordinary Entity has the wrong record kind."""
        return self._index.get(id, Assembly)

    def relationship(self, id: UUID) -> Relationship:
        """Resolve a Relationship in this revision; wrong kind and missing differ."""
        return self._index.get(id, Relationship)

    def value(
        self,
        id: UUID | None = None,
        *,
        owner: UUID | None = None,
        key: str | None = None,
    ) -> Value:
        """Return a Value by its UUID, or by its owner's UUID and its key.

        The owner is the Entity, Assembly, Relationship or Formulation that holds
        the Value; the key is exact and case-sensitive. Unresolved Values are
        returned too. A missing Value raises MissingReferenceError.
        """
        if id is not None and owner is None and key is None:
            return self._index.get(id, Value)
        return self._keyed(Value, id, owner, key)

    def label(
        self,
        id: UUID | None = None,
        *,
        owner: UUID | None = None,
        key: str | None = None,
    ) -> Label:
        """Return a Label by its UUID, or by its owner's UUID and its key.

        The owner is the Entity, Assembly or Relationship that holds the Label;
        the key is exact and case-sensitive. A missing Label raises
        MissingReferenceError.
        """
        if id is not None and owner is None and key is None:
            return self._index.get(id, Label)
        return self._keyed(Label, id, owner, key)

    def _keyed(self, kind: type[K], id, owner, key) -> K:
        if id is not None or owner is None or key is None:
            raise TypeError(
                f"{kind.__name__.lower()} takes an id, or an owner and a key"
            )
        item = self._local(kind, owner, key)
        if item is None:
            record = self._index.records[owner]
            name = getattr(record, "code", None) or owner
            raise MissingReferenceError(
                key,
                kind=kind.__name__,
                by="key",
                where=f"{type(record).__name__} {name}",
                candidates=get_close_matches(
                    key,
                    sorted(k for c, o, k in self._keys if c is kind and o == owner),
                    n=3,
                ),
            )
        return item

    def _local(self, kind: type[K], owner: UUID, key: str) -> K | None:
        """Return the owner's Value or Label with this key, or None when it has none.

        The owner must exist. Tables and selectors use this for an absent cell.
        """
        self._index.get(require_uuid(owner, "owner"), Record)
        identity = self._keys.get((kind, owner, require_text(key, "key")))
        return None if identity is None else cast(K, self._index.records[identity])

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
            **{name: getattr(update, name) for name in SECTIONS},
        )
        check_revision(self._record, candidate)
        return type(self)(candidate, units=self._units)
