"""One immutable finalized execution record; construction performs no execution."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self
from uuid import UUID

from rangekeeper.quantity import UnitSystem
from rangekeeper.run.report import check_local
from rangekeeper.schema.records import Metadata, Report
from rangekeeper.schema.records import Run as RunRecord
from rangekeeper.schema.validation import document_version, supports_version
from rangekeeper.shared.diagnostics import ValidationReport
from rangekeeper.shared.errors import UnsupportedVersionError
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.shared.validation import bounded


def _validate_local(record: RunRecord) -> ValidationReport:
    """Report the local status and report problems of one finalized record."""
    data = record.to_data()
    return bounded(
        [], lambda: check_local(data, document_version("Run")), document=data
    )


@dataclass(frozen=True, init=False, eq=False)
class Run:
    """Locally consistent execution record with immutable generated field access.

    Local construction checks status/report consistency but resolves no references.
    ``validate(resolver=...)`` adds the tree and publication checks.
    Neither operation certifies that the reported computation occurred. A repeated
    execution is another Run; this facade deliberately has no revise operation.
    """

    # ``_validated`` is set by run.validation.mark_validated; it is not a field.
    __slots__ = ("_record", "_validated")
    _record: RunRecord

    def __init__(self, record: RunRecord) -> None:
        if not isinstance(record, RunRecord):
            raise TypeError("record must be a generated Run record")
        version = document_version("Run")
        if not supports_version(record.metadata.schema_version, version):
            raise UnsupportedVersionError(record.metadata.schema_version)
        _validate_local(record).raise_if_invalid()
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "_validated", None)

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

    def validate(
        self,
        *,
        resolver: DocumentResolver | None = None,
        units: UnitSystem | None = None,
    ) -> ValidationReport:
        """Report the problems of this Run; content problems raise nothing.

        Without ``resolver``, the check repeats the local rules of construction.
        With ``resolver``, it also checks the Run tree and the published outputs
        against the exact revisions that they reference
        (``rangekeeper.run.validate``). ``units`` applies to that tree check only.
        """
        from rangekeeper.run.validation import validate_document

        return validate_document(self, resolver=resolver, units=units)

    def check(
        self,
        *,
        resolver: DocumentResolver | None = None,
        units: UnitSystem | None = None,
    ) -> Self:
        """Return this Run if ``validate`` finds no problem.

        Otherwise raise ValidationError; its ``report`` holds the problems.
        """
        self.validate(resolver=resolver, units=units).raise_if_invalid()
        return self

    def __repr__(self) -> str:
        return f"Run(id={self.id!r}, completion={self.report.status.completion!r})"
