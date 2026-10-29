"""The tables that map expected failures and backend terminations to Run statuses.

``Status`` and ``Code`` change together here: each row of ``FAILURES`` gives
the completion, solution, ``Status`` and diagnostic code of one expected error.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from types import MappingProxyType

from rangekeeper.execution.backends.base import Termination
from rangekeeper.schema.records import CompletionStatus, Severity, SolutionStatus
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AttemptDeadlineError,
    BackendUnavailableError,
    NumericalError,
    UnitError,
    UnsupportedError,
    ValidationError,
)


class Status(StrEnum):
    """What an Outcome found, in one word.

    The status follows from the Run report: its completion, its solution and
    the code of its decisive diagnostic.
    """

    FEASIBLE = "feasible"
    """An accepted candidate, and the equations determine each unknown."""
    UNDERDETERMINED = "underdetermined"
    """An accepted candidate, but the equations leave some unknowns free."""
    INFEASIBLE = "infeasible"
    """The backend proved that no candidate satisfies the equations."""
    UNSUPPORTED = "unsupported"
    """The problem is outside the supported mathematics or limits."""
    INVALID = "invalid"
    """The Specification is not valid against its Model."""
    LIMITED = "limited"
    """A time or iteration limit stopped the attempt before a candidate."""
    FAILED = "failed"
    """A numerical, backend or verification failure."""


class Reached(IntEnum):
    """The last stage that an attempt completed."""

    NOTHING = 0
    BOUND = 1
    """``bind_roles`` returned a Binding."""
    SOLVED = 2
    """The backend returned a BackendResult."""


@dataclass(frozen=True)
class Conclusion:
    """The completion, solution, Status and diagnostic of one failed attempt.

    Without ``code``, the error's own code applies.
    """

    completion: CompletionStatus
    solution: SolutionStatus
    status: Status
    code: Code | None
    severity: Severity = Severity.ERROR


@dataclass(frozen=True)
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


FAILED = CompletionStatus.FAILED
NOT_ASSESSED = SolutionStatus.NOT_ASSESSED
UNKNOWN = SolutionStatus.UNKNOWN

# Each expected error, in matching order. Any other error raises to the caller.
FAILURES: tuple[Failure, ...] = (
    Failure(
        (AttemptDeadlineError,),
        Conclusion(
            CompletionStatus.LIMITED,
            NOT_ASSESSED,
            Status.LIMITED,
            Code.ATTEMPT_DEADLINE,
            Severity.WARNING,
        ),
    ),
    Failure(
        (ValidationError,),
        Conclusion(FAILED, NOT_ASSESSED, Status.INVALID, Code.SPECIFICATION_INVALID),
        Reached.BOUND,
        # After binding, only a rejected candidate raises ValidationError.
        Conclusion(FAILED, UNKNOWN, Status.FAILED, Code.NUMERICAL_REJECTION),
    ),
    Failure(
        (UnsupportedError,),
        Conclusion(FAILED, NOT_ASSESSED, Status.UNSUPPORTED, None),
        Reached.SOLVED,
        Conclusion(FAILED, UNKNOWN, Status.UNSUPPORTED, None),
    ),
    Failure(
        (UnitError,),
        Conclusion(
            FAILED, NOT_ASSESSED, Status.UNSUPPORTED, Code.UNSUPPORTED_CAPABILITY
        ),
        Reached.SOLVED,
        Conclusion(FAILED, UNKNOWN, Status.UNSUPPORTED, Code.UNSUPPORTED_CAPABILITY),
    ),
    Failure(
        (BackendUnavailableError,),
        Conclusion(FAILED, NOT_ASSESSED, Status.FAILED, Code.BACKEND_UNAVAILABLE),
    ),
    Failure(
        (NumericalError, ArithmeticError),
        Conclusion(FAILED, UNKNOWN, Status.FAILED, Code.NUMERICAL_FAILURE),
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


def _by_code() -> Mapping[str, Status]:
    """Return the Status of each code in ``FAILURES``; one code has one Status."""
    found: dict[str, Status] = {}
    for item in FAILURES:
        for conclusion in (item.before, item.after):
            if conclusion is None or conclusion.code is None:
                continue
            if found.setdefault(conclusion.code.value, conclusion.status) is not (
                conclusion.status
            ):
                raise AssertionError(f"{conclusion.code} has two statuses")
    return MappingProxyType(found)


_BY_CODE = _by_code()
# A row without a code is for an error that carries its own code.
_OWN_CODE = next(item.before.status for item in FAILURES if item.before.code is None)


def failed(code: str) -> Status:
    """Return the Status of a failed attempt whose decisive diagnostic has ``code``.

    A code that no row of ``FAILURES`` names is an error's own code, such as
    ``nonaffine_unknowns`` or ``symbol_limit``: ``UNSUPPORTED``.
    """
    return _BY_CODE.get(code, _OWN_CODE)


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
    Termination.LIMIT: Ending(CompletionStatus.LIMITED, UNKNOWN, True),
    Termination.ERROR: Ending(FAILED, UNKNOWN, False),
    Termination.UNKNOWN: Ending(CompletionStatus.COMPLETED, UNKNOWN, True),
}
