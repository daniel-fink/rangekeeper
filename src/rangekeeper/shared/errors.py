"""The errors that Rangekeeper raises (ADR-016).

Every error subclasses ``RangekeeperError`` and carries a ``code`` from
``rangekeeper.errors.Code``. Most also subclass the built-in type that callers
caught before, for example ``ValueError``. Owner packages re-export the errors
that their operations raise; ``rangekeeper.errors`` exports all of them.

Every error takes its message first and each field by keyword. The fields of
``ErrorFields`` are common to all errors; a subclass adds its own keywords.
"""

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, Unpack
from uuid import UUID

from rangekeeper.shared.codes import Code

if TYPE_CHECKING:
    # diagnostics imports this module; the annotations only name its types.
    from rangekeeper.shared.diagnostics import Issue, ValidationReport


class ErrorFields(TypedDict, total=False):
    """The keyword fields that every ``RangekeeperError`` takes.

    - ``code``: the ``Code`` of this failure, when the error class has no code
      or another code applies;
    - ``document_id``: the UUID of the document that contains the failure;
    - ``path``: the JSON Pointer of the failure in that document;
    - ``targets``: the UUIDs of the records that the failure is about.

    ``Issue`` has the same fields, so an error and the Issue that a validation
    report makes from it say the same thing.
    """

    code: Code | None
    document_id: UUID | None
    path: str
    targets: Iterable[UUID]


class RangekeeperError(Exception):
    """The base of every error that Rangekeeper raises.

    ``code`` identifies the failure. Read the code and the error's fields, not
    its message. ``document_id``, ``path`` and ``targets`` locate the failure
    when they are known (``ErrorFields``). A class without its own ``code``
    takes one by keyword.
    """

    code: Code

    def __init__(
        self,
        message: str,
        *,
        code: Code | None = None,
        document_id: UUID | None = None,
        path: str = "",
        targets: Iterable[UUID] = (),
    ) -> None:
        super().__init__(message)
        if code is not None:
            self.code = Code(code)
        elif not hasattr(self, "code"):
            raise TypeError(f"{type(self).__name__} takes a code")
        self.document_id = document_id
        self.path = path
        self.targets = tuple(targets)

    def _arguments(self) -> tuple[Any, ...]:
        """Return the positional arguments that make this error again."""
        return (str(self),)

    def _fields(self) -> dict[str, Any]:
        """Return the keyword fields that make this error again.

        A subclass adds its own fields to these. A code that the class gives
        is not repeated.
        """
        return {
            "code": vars(self).get("code"),
            "document_id": self.document_id,
            "path": self.path,
            "targets": self.targets,
        }

    def __reduce__(
        self,
    ) -> tuple[Callable[..., "RangekeeperError"], tuple[Any, ...]]:
        # One reducer for every error: pickling keeps each field.
        return _rebuild, (type(self), self._arguments(), self._fields())


def _rebuild(
    cls: type[RangekeeperError],
    arguments: tuple[Any, ...],
    fields: Mapping[str, Any],
) -> RangekeeperError:
    """Make an error again from its arguments and fields, after pickling."""
    return cls(*arguments, **fields)


class ContractError(RangekeeperError, ValueError):
    """A semantic rule failed, with its code, JSON Pointer and structured fields.

    ``values`` are the named inputs of the failure and ``evidence`` its
    measured results. Validation entrypoints convert this failure into an
    ``Issue`` with the same code and fields.
    """

    code = Code.CONTRACT

    def __init__(
        self,
        message: str,
        *,
        values: Mapping[str, Any] | None = None,
        evidence: Mapping[str, Any] | None = None,
        **fields: Unpack[ErrorFields],
    ) -> None:
        super().__init__(message, **fields)
        self.values = dict(values or {})
        self.evidence = dict(evidence or {})

    def _fields(self) -> dict[str, Any]:
        return {**super()._fields(), "values": self.values, "evidence": self.evidence}

    @classmethod
    def from_issue(cls, issue: "Issue") -> "ContractError":
        """Return a ContractError with the code, message and fields of an Issue."""
        return cls(
            issue.message,
            code=issue.code,
            document_id=issue.document_id,
            path=issue.path,
            targets=issue.targets,
            values=issue.values,
            evidence=issue.evidence,
        )

    def at(self, path: str) -> "ContractError":
        """Return a copy of this error at another JSON Pointer."""
        return ContractError(str(self), **{**self._fields(), "path": path})


class ValidationError(RangekeeperError, ValueError):
    """A document or record failed validation; ``report`` retains diagnostics.

    ``code``, ``document_id``, ``path`` and ``targets`` are those of the first
    issue. Read the other issues from ``report``.
    """

    def __init__(self, report: "ValidationReport") -> None:
        self.report = report
        first = report.issues[0] if report.issues else None
        super().__init__(
            "; ".join(
                f"{issue.path or '/'}: {issue.message}" for issue in report.issues
            ),
            code=Code.CONTRACT if first is None else first.code,
            document_id=None if first is None else first.document_id,
            path="" if first is None else first.path,
            targets=() if first is None else first.targets,
        )

    def _arguments(self) -> tuple[Any, ...]:
        return (self.report,)

    def _fields(self) -> dict[str, Any]:
        # The report gives every field.
        return {}


class UnsupportedVersionError(RangekeeperError, ValueError):
    """A document uses a schema version unsupported by this installed library."""

    code = Code.UNSUPPORTED_VERSION


class _LookupFields(RangekeeperError):
    """The fields and message of a failed lookup; the base of the lookup errors."""

    _verb: str
    _label: str

    def __init__(
        self,
        requested: object,
        *,
        kind: str = "reference",
        by: str = "id",
        where: str | None = None,
        candidates: Iterable[str] = (),
        **fields: Unpack[ErrorFields],
    ) -> None:
        self.requested = requested
        self.kind = kind
        self.by = by
        self.where = where
        self.candidates = tuple(candidates)
        text = repr(requested) if isinstance(requested, str) else str(requested)
        subject = f"{kind} {text}" if by == "id" else f"{kind} with {by} {text}"
        message = f"{subject} {self._verb}" + (f" in {where}" if where else "")
        if self.candidates:
            message += f"; {self._label}: " + ", ".join(self.candidates)
        super().__init__(message + self._detail(), **fields)

    def _detail(self) -> str:
        """Return the end of the message that a subclass adds; empty by default."""
        return ""

    def _arguments(self) -> tuple[Any, ...]:
        return (self.requested,)

    def _fields(self) -> dict[str, Any]:
        return {
            **super()._fields(),
            "kind": self.kind,
            "by": self.by,
            "where": self.where,
            "candidates": self.candidates,
        }


class MissingReferenceError(_LookupFields, LookupError):
    """A lookup by UUID, code, name, key or path found no item.

    ``requested`` is the value that the caller gave and ``by`` says what it is:
    ``"id"``, ``"code"``, ``"name"``, ``"key"`` or ``"path"``. ``kind`` names the
    kind of item, and ``where`` names the document, store or owner that was
    searched. ``candidates`` gives the nearest names that exist, when any are close.
    ``referenced_by`` names what still references the item, when it is known:
    the keys of the equations that use a value that a draft removed.
    """

    code = Code.REFERENCE_MISSING
    _verb = "not found"
    _label = "nearest"

    def __init__(
        self,
        requested: object,
        *,
        kind: str = "reference",
        by: str = "id",
        where: str | None = None,
        candidates: Iterable[str] = (),
        referenced_by: Iterable[str] = (),
        **fields: Unpack[ErrorFields],
    ) -> None:
        self.referenced_by = tuple(referenced_by)
        super().__init__(
            requested, kind=kind, by=by, where=where, candidates=candidates, **fields
        )

    def _detail(self) -> str:
        if not self.referenced_by:
            return ""
        return "; referenced by: " + ", ".join(self.referenced_by)

    def _fields(self) -> dict[str, Any]:
        return {**super()._fields(), "referenced_by": self.referenced_by}


class AmbiguousReferenceError(_LookupFields, LookupError):
    """A lookup for one item by code or name found several items.

    The fields are those of ``MissingReferenceError``. ``candidates`` gives the
    code, or else the UUID, of each item that matched, in declaration order.
    """

    code = Code.REFERENCE_AMBIGUOUS
    _verb = "is ambiguous"
    _label = "matches"


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

    def __init__(
        self,
        message: str,
        *,
        suggestions: Iterable[str] = (),
        **fields: Unpack[ErrorFields],
    ) -> None:
        super().__init__(message, **fields)
        self.suggestions = tuple(suggestions)

    def _fields(self) -> dict[str, Any]:
        return {**super()._fields(), "suggestions": self.suggestions}


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
    """The complete file is visible, but its durability was not confirmed.

    ``file`` is the published file; ``filename`` gives it as text, as for any
    ``OSError``. The ``OSError`` that stopped the confirmation is the cause
    (``__cause__``).
    """

    code = Code.PUBLISHED_FILE
    published = True

    def __init__(
        self,
        message: str,
        *,
        file: Path,
        **fields: Unpack[ErrorFields],
    ) -> None:
        super().__init__(message, **fields)
        self.file = file
        self.filename = str(file)

    def _fields(self) -> dict[str, Any]:
        return {**super()._fields(), "file": self.file}


class UnsupportedError(RangekeeperError, ValueError):
    """A declared problem or expression is outside the supported capability.

    ``document_id`` and ``targets`` locate the declaration when they are known:
    the document and the Constraint. ``equation`` is the text of that
    declaration, for example ``"noi = coverage * debt_service"``. With the code
    ``nonaffine_unknowns``, ``unknowns`` gives the keys of the unknowns in the
    term that is not affine.
    """

    code = Code.UNSUPPORTED_CAPABILITY

    def __init__(
        self,
        message: str,
        *,
        equation: str | None = None,
        unknowns: Iterable[str] = (),
        **fields: Unpack[ErrorFields],
    ) -> None:
        super().__init__(message, **fields)
        self.equation = equation
        self.unknowns = tuple(unknowns)

    def _fields(self) -> dict[str, Any]:
        return {
            **super()._fields(),
            "equation": self.equation,
            "unknowns": self.unknowns,
        }


class NumericalError(RangekeeperError, ValueError):
    """Arithmetic or a backend candidate cannot support numerical acceptance.

    The code is ``numerical_failure``, ``numerical_rejection`` when
    verification rejected a candidate, or the code of a more specific failure,
    such as ``no_sign_change`` for an IRR. ``values`` are the named values of
    the failure, such as the totals of the inflows and outflows of an IRR.
    """

    code = Code.NUMERICAL_FAILURE

    def __init__(
        self,
        message: str,
        *,
        values: Mapping[str, Any] | None = None,
        **fields: Unpack[ErrorFields],
    ) -> None:
        super().__init__(message, **fields)
        self.values = dict(values or {})

    def _fields(self) -> dict[str, Any]:
        return {**super()._fields(), "values": self.values}


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

    def __init__(
        self,
        message: str,
        *,
        suggestions: Iterable[str] = (),
        **fields: Unpack[ErrorFields],
    ) -> None:
        super().__init__(message, **fields)
        self.suggestions = tuple(suggestions)

    def _fields(self) -> dict[str, Any]:
        return {**super()._fields(), "suggestions": self.suggestions}


class ExtensionConflictError(RangekeeperError, ValueError):
    """Two implementations claim one name at one extension point."""

    code = Code.EXTENSION_CONFLICT


class EquationError(RangekeeperError, ValueError):
    """Equation text that does not make an equation, with the part that fails.

    ``text`` is the equation text, and ``text[start:end]`` is the part that
    fails; the message marks it. ``code`` says why: ``EQUATION_SYNTAX`` for
    text that does not parse, ``REFERENCE_MISSING`` or ``REFERENCE_AMBIGUOUS``
    for a name that matches no value or several, ``UNITS`` for the units of a
    literal, ``EQUATION_FUNCTION`` for a function, method or member that
    equation text cannot use, and ``PREDICATE`` for text that is not Boolean,
    such as an expression with no comparison. ``suggestions`` gives text to try
    instead, when any is close.
    """

    code = Code.EQUATION_SYNTAX

    def __init__(
        self,
        message: str,
        *,
        text: str,
        start: int,
        end: int,
        suggestions: Iterable[str] = (),
        **fields: Unpack[ErrorFields],
    ) -> None:
        super().__init__(message, **fields)
        self.text = text
        self.start = start
        self.end = end
        self.suggestions = tuple(suggestions)

    def __str__(self) -> str:
        marker = " " * self.start + "^" * max(self.end - self.start, 1)
        return f"{self.args[0]}\n  {self.text}\n  {marker}"

    def _arguments(self) -> tuple[Any, ...]:
        # The message without the text and the marker that ``__str__`` adds.
        return (self.args[0],)

    def _fields(self) -> dict[str, Any]:
        return {
            **super()._fields(),
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "suggestions": self.suggestions,
        }
