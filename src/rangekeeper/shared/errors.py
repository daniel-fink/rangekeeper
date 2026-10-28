"""Errors shared by the schema-derived record boundary."""

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from rangekeeper.shared.codes import Code


class ContractError(ValueError):
    """A semantic rule failed, with its code, JSON Pointer and structured fields.

    The message remains the exception text. Validation entrypoints convert this
    failure into an ``Issue`` with the same code, targets, values and evidence.
    """

    def __init__(
        self,
        message: str,
        *,
        code: Code = Code.CONTRACT,
        path: str = "",
        document_id: UUID | None = None,
        targets: Iterable[UUID] = (),
        values: Mapping[str, Any] | None = None,
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = Code(code)
        self.path = path
        self.document_id = document_id
        self.targets = tuple(targets)
        self.values = dict(values or {})
        self.evidence = dict(evidence or {})

    @classmethod
    def from_issue(cls, issue) -> "ContractError":
        """Return a ContractError with the code, message and fields of an Issue."""
        return cls(
            issue.message,
            code=issue.code,
            path=issue.path,
            document_id=issue.document_id,
            targets=issue.targets,
            values=issue.values,
            evidence=issue.evidence,
        )

    def at(self, path: str) -> "ContractError":
        """Return a copy of this error at another JSON Pointer."""
        return ContractError(
            str(self),
            code=self.code,
            path=path,
            document_id=self.document_id,
            targets=self.targets,
            values=self.values,
            evidence=self.evidence,
        )


class ValidationError(ValueError):
    """A document or record failed validation; ``report`` retains diagnostics."""

    def __init__(self, report):
        self.report = report
        super().__init__(
            "; ".join(
                f"{issue.path or '/'}: {issue.message}" for issue in report.issues
            )
        )


class UnsupportedVersionError(ValueError):
    """A document uses a schema version unsupported by this installed library."""


class MissingReferenceError(LookupError):
    """A UUID does not exist in the requested document or resolver scope."""


class ReferenceTypeError(TypeError):
    """A resolved UUID names a different kind of record than the caller requested."""


class IdentityConflictError(ValueError):
    """One identity is declared more than once or resolves to conflicting content."""


class RevisionConflictError(ValueError):
    """A revision request conflicts with identity, lineage, or revision content."""


class UnitError(ValueError):
    """Units are unknown, malformed, incompatible, or produce a non-finite result.

    ``suggestions`` gives the spellings to try instead, when the registry knows any.
    """

    def __init__(self, message: str, *, suggestions: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.suggestions = tuple(suggestions)


class DecodeError(ValueError):
    """Interchange text or a storage envelope cannot be decoded unambiguously."""


class BoundaryError(Exception):
    """Base for invalid requests or representations crossing an API boundary."""


class EncodingError(BoundaryError, ValueError):
    """A value cannot be represented by the declared boundary contract."""


class ValueEncodingError(EncodingError):
    """Internal scalar encoding failure; consumers translate into their own errors."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")
