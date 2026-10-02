"""One immutable finalized execution record; construction performs no execution."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from .._schema.records import Run as RunRecord, Metadata, Report
from .._schema.validation import document_version
from .._validation import bounded
from ..errors import UnsupportedVersionError
from ._validation import validate_local


@dataclass(frozen=True, init=False, eq=False)
class Run:
    """Locally consistent execution record with immutable generated field access.

    Local construction checks status/report consistency but resolves no references.
    Use run.validation.validate with a resolver for tree and publication checks.
    Neither operation certifies that the reported computation occurred. A repeated
    execution is another Run; this facade deliberately has no revise operation.
    """

    __slots__ = ("_record",)
    _record: RunRecord

    def __init__(self, record: RunRecord) -> None:
        if not isinstance(record, RunRecord):
            raise TypeError("record must be a generated Run record")
        version = document_version("Run")
        if record.metadata.schema_version != version:
            raise UnsupportedVersionError(record.metadata.schema_version)
        data = record.to_data()
        bounded(
            [], lambda: validate_local(data, version), document=data
        ).raise_if_invalid()
        object.__setattr__(self, "_record", record)

    @classmethod
    def from_data(cls, data: Mapping[str, object]) -> "Run":
        """Copy/freeze and check shape/local rules; raise before publishing on failure."""
        return cls(RunRecord.from_data(data))

    @property
    def id(self) -> UUID:
        """Identity of this finalized revision, forwarded from Metadata."""
        return self.metadata.id

    @property
    def metadata(self) -> Metadata:
        """Immutable revision identity, version, lineage, and description."""
        return self._record.metadata

    @property
    def record(self) -> RunRecord:
        """Typed read-only access to the authoritative generated fields."""
        return self._record

    @property
    def report(self) -> Report:
        """Recorded outcome and evidence; this is a declaration, not solver proof."""
        return self._record.report

    def to_data(self) -> dict[str, object]:
        """Return detached data, preserving omitted/null fields and trace order."""
        return self._record.to_data()

    def __repr__(self) -> str:
        return f"Run(id={self.id!r}, completion={self.report.status.completion!r})"
