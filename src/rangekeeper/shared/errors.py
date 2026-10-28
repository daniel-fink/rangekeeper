"""The errors that Rangekeeper raises (ADR-016).

Every error subclasses ``RangekeeperError`` and carries a ``code`` from
``rangekeeper.errors.Code``. Most also subclass the built-in type that callers
caught before, for example ``ValueError``. Owner packages re-export the errors
that their operations raise; ``rangekeeper.errors`` exports all of them.
"""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

from rangekeeper.shared.codes import Code


class RangekeeperError(Exception):
    """The base of every error that Rangekeeper raises.

    ``code`` identifies the failure. Read the code and the error's fields, not
    its message.
    """

    code: Code


class ContractError(RangekeeperError, ValueError):
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


class ValidationError(RangekeeperError, ValueError):
    """A document or record failed validation; ``report`` retains diagnostics.

    ``code`` is the code of the first issue.
    """

    def __init__(self, report):
        self.report = report
        self.code = report.issues[0].code if report.issues else Code.CONTRACT
        super().__init__(
            "; ".join(
                f"{issue.path or '/'}: {issue.message}" for issue in report.issues
            )
        )


class UnsupportedVersionError(RangekeeperError, ValueError):
    """A document uses a schema version unsupported by this installed library."""

    code = Code.UNSUPPORTED_VERSION


class MissingReferenceError(RangekeeperError, LookupError):
    """A UUID does not exist in the requested document or resolver scope."""

    code = Code.REFERENCE_MISSING


class ReferenceTypeError(RangekeeperError, TypeError):
    """A resolved UUID names a different kind of record than the caller requested."""

    code = Code.REFERENCE_KIND


class IdentityConflictError(RangekeeperError, ValueError):
    """One identity is declared more than once or resolves to conflicting content."""

    code = Code.REFERENCE_IDENTITY


class RevisionConflictError(RangekeeperError, ValueError):
    """A revision request conflicts with identity, lineage, or revision content."""

    code = Code.REVISION_CONFLICT


class UnitError(RangekeeperError, ValueError):
    """Units are unknown, malformed, incompatible, or produce a non-finite result.

    ``suggestions`` gives the spellings to try instead, when the registry knows any.
    """

    code = Code.UNITS

    def __init__(self, message: str, *, suggestions: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.suggestions = tuple(suggestions)


class DecodeError(RangekeeperError, ValueError):
    """Interchange text or a storage envelope cannot be decoded unambiguously."""

    code = Code.DECODE


class EncodingError(RangekeeperError, ValueError):
    """A value cannot be represented by the declared boundary contract."""

    code = Code.ENCODING


class TableError(RangekeeperError, ValueError):
    """Invalid table columns, row shape, or duplicate row identity."""

    code = Code.TABLE


class PublishedFileError(RangekeeperError, OSError):
    """The complete file is visible, but its durability was not confirmed."""

    code = Code.PUBLISHED_FILE
    published = True

    def __init__(self, path: Path, error: OSError):
        self.path = path
        self.error = error
        super().__init__(
            error.errno,
            f"File published; durability was not confirmed: {error}",
            str(path),
        )


class UnsupportedError(RangekeeperError, ValueError):
    """A declared problem or expression is outside the supported capability.

    ``document`` and ``target`` locate the declaration when they are known.
    """

    def __init__(
        self,
        message: str,
        *,
        code: Code = Code.UNSUPPORTED_CAPABILITY,
        document: UUID | None = None,
        target: UUID | None = None,
    ) -> None:
        super().__init__(message)
        self.code = Code(code)
        self.document = document
        self.target = target


class NumericalError(RangekeeperError, ValueError):
    """Arithmetic or a backend candidate cannot support numerical acceptance."""

    code = Code.NUMERICAL_FAILURE


class BackendUnavailableError(RangekeeperError, RuntimeError):
    """The optional, pinned execution backend cannot be loaded."""

    code = Code.BACKEND_UNAVAILABLE


class AttemptDeadlineError(RangekeeperError, RuntimeError):
    """The attempt budget expired at a preparation or compilation checkpoint."""

    code = Code.ATTEMPT_DEADLINE


class UnknownExtensionError(RangekeeperError, LookupError):
    """An extension point has no implementation with the requested name.

    ``suggestions`` gives the registered names to try instead, when any are close.
    """

    code = Code.EXTENSION_UNKNOWN

    def __init__(self, message: str, *, suggestions: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.suggestions = tuple(suggestions)


class ExtensionConflictError(RangekeeperError, ValueError):
    """Two implementations claim one name at one extension point."""

    code = Code.EXTENSION_CONFLICT
