"""A saved investigation contribution, distinct from its derived composition."""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from uuid import UUID

from .._comparison import canonical
from .._schema.records import Specification as SpecificationRecord, Metadata
from .._schema.validation import document_version
from .._validation import bounded, require
from ..errors import RevisionConflictError, UnsupportedVersionError
from ..model._index import Index
from ..model._formulation import validate_formulation_names
from ._composition import compose_specification, validate_local_header


def _validate_local(record: SpecificationRecord) -> None:
    """Check local ownership and roles while permitting unresolved external inputs."""
    data = record.to_data()
    index = Index.build(record)
    version = document_version("Specification")
    if record.metadata.schema_version != version:
        raise UnsupportedVersionError(record.metadata.schema_version)

    def check():
        validate_local_header(data, version)
        index.check_known_references(record)
        require(
            record.metadata.previous not in index.records,
            "Specification predecessor targets current scope",
        )
        # Includes and cases are external edges. Validate this contribution's own
        # additive rules with those edges absent; do not fabricate referenced docs.
        isolated = {
            key: value
            for key, value in data.items()
            if key not in ("includes", "cases")
        }
        compose_specification(isolated, {}, version)
        for field in ("includes", "cases"):
            require(
                all(
                    identity not in index.records
                    for identity in (getattr(record, field) or ())
                ),
                f"{field} reference targets a local declaration",
            )
        if record.model is not None:
            require(
                record.model not in index.records,
                "Model pin targets a local declaration",
            )
        for value in (data.get("settings") or {}).values():
            require(
                value is None or math.isfinite(value) and value > 0,
                "settings must be positive and finite",
            )

        validate_formulation_names(data.get("formulations") or [])

    bounded([], check, document=data).raise_if_invalid()


@dataclass(frozen=True, init=False, eq=False)
class Specification:
    """Immutable locally valid contribution, including partial contributions/batches.

    External resolution and complete solve roles belong to composition validation.
    The ``record`` property exposes all generated fields with their original types;
    this facade does not redeclare the authoritative field schema.
    """

    __slots__ = ("_record",)
    _record: SpecificationRecord

    def __init__(self, record: SpecificationRecord) -> None:
        if not isinstance(record, SpecificationRecord):
            raise TypeError("record must be a generated Specification record")
        _validate_local(record)
        object.__setattr__(self, "_record", record)

    @classmethod
    def from_data(cls, data: Mapping[str, object]) -> "Specification":
        """Copy and validate local structure/ownership; perform no external lookup."""
        return cls(SpecificationRecord.from_data(data))

    @property
    def id(self) -> UUID:
        """Saved revision identity, forwarded from Metadata."""
        return self.metadata.id

    @property
    def metadata(self) -> Metadata:
        """Immutable revision identity, version, lineage and descriptive content."""
        return self._record.metadata

    @property
    def record(self) -> SpecificationRecord:
        """Read-only typed access to assignments, roles, include/case edges and settings."""
        return self._record

    def to_data(self) -> dict[str, object]:
        """Export detached saved content, retaining include/case boundaries and presence."""
        return self._record.to_data()

    def __repr__(self) -> str:
        return f"Specification(id={self.id!r}, includes={len(self.record.includes or ())}, cases={len(self.record.cases or ())})"

    def revise(self, replacement: SpecificationRecord) -> "Specification":
        """Accept a complete locally valid replacement with explicit new identity/lineage.

        No include is resolved and no missing requirement is inherited implicitly.
        Metadata-only identity changes and schema-version migrations are rejected.
        """
        if not isinstance(replacement, SpecificationRecord):
            raise TypeError("replacement must be a generated Specification record")
        if (
            replacement.metadata.id in (self.id, self.metadata.previous)
            or replacement.metadata.previous != self.id
        ):
            raise RevisionConflictError(
                "replacement must not reuse this revision or its predecessor, and must set previous=current UUID"
            )
        if replacement.metadata.schema_version != self.metadata.schema_version:
            raise UnsupportedVersionError("revise cannot migrate schema versions")
        before, after = self.to_data(), replacement.to_data()
        for data, metadata in ((before, self.metadata), (after, replacement.metadata)):
            data["metadata"] = {
                key: value
                for key, value in metadata.to_data().items()
                if key not in ("id", "previous")
            }
        if canonical("Specification", before) == canonical("Specification", after):
            raise RevisionConflictError(
                "replacement changes no requirements or descriptive content"
            )
        return type(self)(replacement)
