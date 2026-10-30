"""The tables that map expected failures and backend terminations to Run statuses.

``Status``, ``Code`` and the error that ``raise_for_status()`` raises change
together here: each row of ``FAILURES`` gives the completion, solution,
``Status``, diagnostic code and error class of one expected error. ``Status``
itself lives in the leaf module ``execution.status``.

``diagnosed`` writes the fields of an expected error into the values of its
diagnostic, and ``rebuilt`` reads them back into the same error class.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID

from rangekeeper.execution.backends.base import Termination
from rangekeeper.execution.errors import OutcomeError
from rangekeeper.execution.status import Status
from rangekeeper.schema.records import (
    CompletionStatus,
    Diagnostic,
    Reference,
    Severity,
    SolutionStatus,
)
from rangekeeper.schema.runtime import JSONValue
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import (
    AttemptDeadlineError,
    BackendUnavailableError,
    NumericalError,
    RangekeeperError,
    UnitError,
    UnsupportedError,
    ValidationError,
)


class Reached(IntEnum):
    """The last stage that an attempt completed."""

    NOTHING = 0
    BOUND = 1
    """``bind_roles`` returned a Binding."""
    SOLVED = 2
    """The backend returned a BackendResult."""


@dataclass(frozen=True, kw_only=True)
class Conclusion:
    """The completion, solution, Status, diagnostic and error of one failed attempt.

    ``code`` is the code of the diagnostic. Without it, the error's own code
    applies: one of ``codes``. ``raises`` is the error class that
    ``Outcome.raise_for_status()`` raises for this conclusion.
    """

    completion: CompletionStatus = CompletionStatus.FAILED
    solution: SolutionStatus
    status: Status
    code: Code | None = None
    codes: tuple[Code, ...] = ()
    raises: type[RangekeeperError]
    severity: Severity = Severity.ERROR

    @property
    def names(self) -> tuple[Code, ...]:
        """Return each diagnostic code that this conclusion can record."""
        return self.codes if self.code is None else (self.code,)


@dataclass(frozen=True, kw_only=True)
class Failure:
    """How one kind of expected error ends an attempt.

    ``after`` applies when the attempt had reached ``boundary`` before the error;
    ``before`` applies otherwise.
    """

    errors: tuple[type[BaseException], ...]
    before: Conclusion
    boundary: Reached | None = None
    after: Conclusion | None = None

    def conclusion(self, reached: Reached) -> Conclusion:
        """Return the status for an attempt that reached ``reached``."""
        if self.boundary is not None and self.after is not None:
            if reached >= self.boundary:
                return self.after
        return self.before


NOT_ASSESSED = SolutionStatus.NOT_ASSESSED
UNKNOWN = SolutionStatus.UNKNOWN
# The codes that an UnsupportedError carries. A new code needs a place here,
# or its Outcome reads as FAILED.
UNSUPPORTED_CODES = (
    Code.UNSUPPORTED_CAPABILITY,
    Code.NONAFFINE_UNKNOWNS,
    Code.SYMBOL_LIMIT,
    Code.CONSTRAINT_LIMIT,
)
# The codes that a NumericalError carries: a failed calculation, or no active
# side of each max or min that holds at its solution (#308).
NUMERICAL_CODES = (Code.NUMERICAL_FAILURE, Code.ACTIVE_SIDE)

# Each expected error, in matching order. Any other error raises to the caller.
FAILURES: tuple[Failure, ...] = (
    Failure(
        errors=(AttemptDeadlineError,),
        before=Conclusion(
            completion=CompletionStatus.LIMITED,
            solution=NOT_ASSESSED,
            status=Status.LIMITED,
            code=Code.ATTEMPT_DEADLINE,
            raises=AttemptDeadlineError,
            severity=Severity.WARNING,
        ),
    ),
    Failure(
        errors=(ValidationError,),
        before=Conclusion(
            solution=NOT_ASSESSED,
            status=Status.INVALID,
            code=Code.SPECIFICATION_INVALID,
            raises=ValidationError,
        ),
        boundary=Reached.BOUND,
        # After binding, only a rejected candidate raises ValidationError.
        after=Conclusion(
            solution=UNKNOWN,
            status=Status.FAILED,
            code=Code.NUMERICAL_REJECTION,
            raises=NumericalError,
        ),
    ),
    Failure(
        errors=(UnsupportedError,),
        before=Conclusion(
            solution=NOT_ASSESSED,
            status=Status.UNSUPPORTED,
            codes=UNSUPPORTED_CODES,
            raises=UnsupportedError,
        ),
        boundary=Reached.SOLVED,
        after=Conclusion(
            solution=UNKNOWN,
            status=Status.UNSUPPORTED,
            codes=UNSUPPORTED_CODES,
            raises=UnsupportedError,
        ),
    ),
    # Units that do not agree make the problem invalid, not unsupported (ADR-016).
    Failure(
        errors=(UnitError,),
        before=Conclusion(
            solution=NOT_ASSESSED,
            status=Status.INVALID,
            code=Code.INCOMPATIBLE_UNITS,
            raises=UnitError,
        ),
        boundary=Reached.SOLVED,
        after=Conclusion(
            solution=UNKNOWN,
            status=Status.INVALID,
            code=Code.INCOMPATIBLE_UNITS,
            raises=UnitError,
        ),
    ),
    Failure(
        errors=(BackendUnavailableError,),
        before=Conclusion(
            solution=NOT_ASSESSED,
            status=Status.FAILED,
            code=Code.BACKEND_UNAVAILABLE,
            raises=BackendUnavailableError,
        ),
    ),
    Failure(
        errors=(NumericalError,),
        before=Conclusion(
            solution=UNKNOWN,
            status=Status.FAILED,
            codes=NUMERICAL_CODES,
            raises=NumericalError,
        ),
    ),
    Failure(
        errors=(ArithmeticError,),
        before=Conclusion(
            solution=UNKNOWN,
            status=Status.FAILED,
            code=Code.NUMERICAL_FAILURE,
            raises=NumericalError,
        ),
    ),
)

EXPECTED: tuple[type[BaseException], ...] = tuple(
    error for failure in FAILURES for error in failure.errors
)


def failure(error: BaseException, reached: Reached) -> Conclusion:
    """Return the conclusion of an attempt that ``error`` ended after ``reached``."""
    for item in FAILURES:
        if isinstance(error, item.errors):
            return item.conclusion(reached)
    raise LookupError(f"{type(error).__name__} is not an expected failure")


def _by_code() -> Mapping[str, Conclusion]:
    """Return the conclusion of each code in ``FAILURES``.

    One code has one Status and one error class.
    """
    found: dict[str, Conclusion] = {}
    conclusions = [item.before for item in FAILURES]
    conclusions += [item.after for item in FAILURES if item.after is not None]
    for conclusion in conclusions:
        for code in conclusion.names:
            known = found.setdefault(code.value, conclusion)
            if (known.status, known.raises) != (conclusion.status, conclusion.raises):
                raise AssertionError(f"{code} has two statuses or errors")
    return MappingProxyType(found)


BY_CODE = _by_code()
"""The conclusion of each code that an expected failure records."""


def failed(code: str) -> Status:
    """Return the Status of a failed attempt whose decisive diagnostic has ``code``.

    A code that no row of ``FAILURES`` names is a failure without its own
    error, such as ``numerical_rejection`` from verification: ``FAILED``.
    """
    found = BY_CODE.get(code)
    return Status.FAILED if found is None else found.status


def diagnosed(error: BaseException) -> dict[str, JSONValue]:
    """Return the structured fields of an expected error, as diagnostic values.

    A reader of the Run then needs no message text: ``issues`` for a
    ValidationError, ``equation`` and ``unknowns`` for an UnsupportedError,
    and ``path`` and ``targets`` when the error has them and the diagnostic's
    own ``document`` and ``target`` cannot hold them.
    """
    values: dict[str, JSONValue] = {}
    if isinstance(error, ValidationError):
        values["issues"] = [_issue_values(issue) for issue in error.report.issues]
        return values
    if isinstance(error, UnsupportedError):
        if error.equation is not None:
            values["equation"] = error.equation
        if error.unknowns:
            values["unknowns"] = list(error.unknowns)
    if isinstance(error, RangekeeperError):
        if error.path:
            values["path"] = error.path
        if len(error.targets) > 1:
            values["targets"] = [str(target) for target in error.targets]
    return values


def referenced(error: BaseException) -> tuple[Reference, ...]:
    """Return the Values and Movements that the diagnostic of ``error`` references.

    A ``nonaffine_unknowns`` failure references the unknowns of the term that
    is not affine, as ``underdetermined`` references its free unknowns. The
    compiler's error has them as its targets; ``compile`` scopes that error to
    the Constraint and keeps it as the cause. Other errors reference nothing.
    """
    if not isinstance(error, UnsupportedError):
        return ()
    cause = error.__cause__
    if (
        error.code is not Code.NONAFFINE_UNKNOWNS
        or not isinstance(cause, UnsupportedError)
        or cause.code is not Code.NONAFFINE_UNKNOWNS
    ):
        return ()
    return tuple(Reference(target=identity) for identity in cause.targets)


def rebuilt(
    diagnostic: Diagnostic, *, message: str, status: Status
) -> RangekeeperError:
    """Return the error that ``raise_for_status()`` raises for a decisive diagnostic.

    The class comes from ``FAILURES``: ``OutcomeError`` for a code that no row
    names. The error has the diagnostic's code and the fields that
    ``diagnosed`` wrote.
    """
    values = _values(diagnostic)
    found = BY_CODE.get(diagnostic.code)
    kind = OutcomeError if found is None else found.raises
    if kind is ValidationError:
        return ValidationError(_report(values, message))
    fields: dict[str, Any] = {
        "code": Code(diagnostic.code),
        "document_id": _uuid(diagnostic.document),
        "path": _text(values.get("path")) or "",
        "targets": _targets(diagnostic, values),
    }
    if kind is UnsupportedError:
        fields["equation"] = _text(values.get("equation"))
        fields["unknowns"] = _words(values.get("unknowns"))
    if kind is OutcomeError:
        fields["status"] = status
    return kind(message, **fields)


def _issue_values(issue: Issue) -> dict[str, JSONValue]:
    """Return one validation issue as JSON, with each of its fields."""
    return {
        "code": issue.code.value,
        "message": issue.message,
        "document": None if issue.document_id is None else str(issue.document_id),
        "path": issue.path,
        "targets": [str(target) for target in issue.targets],
        "values": _json(issue.values),
        "evidence": _json(issue.evidence),
    }


def _report(values: Mapping[str, Any], message: str) -> ValidationReport:
    """Return the validation report that ``diagnosed`` wrote, issue by issue.

    A diagnostic without issues, from a Run of an older version, gives one
    ``specification_invalid`` issue with the message.
    """
    issues = values.get("issues")
    if not isinstance(issues, (list, tuple)) or not issues:
        return ValidationReport((Issue(Code.SPECIFICATION_INVALID, message),))
    return ValidationReport(tuple(_issue(item) for item in issues))


def _issue(values: Mapping[str, Any]) -> Issue:
    """Return one Issue that ``_issue_values`` wrote. Its values stay JSON."""
    return Issue(
        Code(values["code"]),
        str(values["message"]),
        _uuid(values.get("document")),
        str(values.get("path") or ""),
        tuple(UUID(str(target)) for target in values.get("targets") or ()),
        values.get("values"),
        values.get("evidence"),
    )


def _json(value: object) -> JSONValue:
    """Return a value as JSON: text for a UUID, an enum's value, lists for tuples."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Enum):
        return _json(value.value)
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json(item) for item in value]
    return str(value)


def _values(diagnostic: Diagnostic) -> Mapping[str, Any]:
    values = diagnostic.values
    return values if isinstance(values, Mapping) else {}


def _uuid(value: object) -> UUID | None:
    if value is None or isinstance(value, UUID):
        return value
    return UUID(str(value))


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _words(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _targets(diagnostic: Diagnostic, values: Mapping[str, Any]) -> tuple[UUID, ...]:
    listed = values.get("targets")
    if isinstance(listed, (list, tuple)):
        return tuple(UUID(str(item)) for item in listed)
    target = _uuid(diagnostic.target)
    return () if target is None else (target,)


@dataclass(frozen=True)
class Ending:
    """The status that a backend termination gives, before verification.

    With ``verify``, a candidate is verified: an accepted candidate is
    ``feasible``. Otherwise the solution stays ``solution``.
    """

    completion: CompletionStatus
    solution: SolutionStatus
    verify: bool


# Each backend termination. Only verification makes a solution feasible.
TERMINATIONS: dict[Termination, Ending] = {
    Termination.FEASIBLE: Ending(CompletionStatus.COMPLETED, UNKNOWN, True),
    Termination.INFEASIBLE: Ending(
        CompletionStatus.COMPLETED, SolutionStatus.INFEASIBLE, False
    ),
    Termination.LIMITED: Ending(CompletionStatus.LIMITED, UNKNOWN, True),
    Termination.FAILED: Ending(CompletionStatus.FAILED, UNKNOWN, False),
    Termination.UNKNOWN: Ending(CompletionStatus.COMPLETED, UNKNOWN, True),
}
