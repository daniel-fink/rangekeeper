"""One self-contained, immutable Model revision and its derived lookup indexes."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

from .._comparison import canonical
from .._records import Record, UNSET, Unset
from .._schema.records import (
    Model as ModelRecord,
    Metadata,
    Definitions,
    System,
    Provenance,
    Entity,
    Relationship,
    Value,
    Formulation,
)
from .._schema.validation import document_version
from ..errors import RevisionConflictError, UnsupportedVersionError
from ..units import UnitSystem, default_units
from ..validate import require_uuid, optional_text
from ._index import Index
from .update import Update


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
    _index: Index
    _units: UnitSystem

    def __init__(
        self, record: ModelRecord, *, units: UnitSystem = default_units
    ) -> None:
        if not isinstance(record, ModelRecord):
            raise TypeError("record must be a generated Model record")
        if not isinstance(units, UnitSystem):
            raise TypeError("units must be a UnitSystem")
        if record.metadata.schema_version != document_version("Model"):
            raise UnsupportedVersionError(record.metadata.schema_version)
        index = Index.build(record)
        from .validation import validate

        validate(record, units=units).raise_if_invalid()
        # Publish state only after both structural/local indexes and semantics pass.
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "_index", index)
        object.__setattr__(self, "_units", units)

    @classmethod
    def from_data(
        cls, data: Mapping[str, object], *, units: UnitSystem = default_units
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
        units: UnitSystem = default_units,
    ) -> "Model":
        """Author a complete Model with typed sections and the same validation path."""
        return cls(
            ModelRecord(
                metadata=metadata,
                definitions=definitions,
                system=system,
                provenance=provenance,
            ),
            units=units,
        )

    @property
    def id(self) -> UUID:
        """The revision UUID, forwarded from Metadata; not a second identity."""
        return self.metadata.id

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

    def to_data(self) -> dict[str, object]:
        """Export detached data, preserving presence and original collection order."""
        return self._record.to_data()

    def __repr__(self) -> str:
        return f"Model(id={self.id!r}, declarations={len(self._index.records) - 1})"

    def entity(self, id: UUID) -> Entity:
        """Resolve an Entity or canonical Assembly; no code/name or history fallback."""
        return self._index.get(id, Entity)

    def relationship(self, id: UUID) -> Relationship:
        """Resolve a Relationship in this revision; wrong kind and missing differ."""
        return self._index.get(id, Relationship)

    def value(self, id: UUID) -> Value:
        """Resolve a domain-owned or Formulation-local Value, including unresolved ones."""
        return self._index.get(id, Value)

    def formulation(self, id: UUID) -> Formulation:
        """Resolve a root or nested Formulation without flattening its ownership."""
        return self._index.get(id, Formulation)

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

        Classification descendants are not implicitly included. Empty results are
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
        candidate = self._record.to_data()
        for section in ("definitions", "system", "provenance"):
            value = getattr(update, section)
            if value is not UNSET:
                candidate[section] = value.to_data()
        if isinstance(update.metadata, Unset):
            metadata = Metadata.from_data(
                {
                    **self.metadata.to_data(),
                    "id": str(uuid4()),
                    "previous": str(self.id),
                }
            )
        else:
            metadata = update.metadata
            if (
                metadata.id in (self.id, self.metadata.previous)
                or metadata.previous != self.id
            ):
                raise RevisionConflictError(
                    "new metadata must not reuse this revision or its predecessor, and must set previous=current UUID"
                )
            if metadata.schema_version != self.metadata.schema_version:
                raise UnsupportedVersionError("revise cannot migrate schema versions")
        proposed_metadata = metadata.to_data()
        candidate["metadata"] = proposed_metadata
        before = self.to_data()
        for data, item in ((before, self.metadata), (candidate, metadata)):
            # Identity/lineage changes alone do not warrant a new domain revision.
            data["metadata"] = {
                k: v for k, v in item.to_data().items() if k not in ("id", "previous")
            }
        if canonical("Model", before) == canonical("Model", candidate):
            raise RevisionConflictError(
                "update changes no domain or descriptive content"
            )
        candidate["metadata"] = proposed_metadata
        return type(self).from_data(candidate, units=self._units)
