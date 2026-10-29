"""The tables that map expected failures and backend terminations to Run statuses."""

from dataclasses import dataclass
from enum import IntEnum

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


class Reached(IntEnum):
    """The last stage that an attempt completed."""

    NOTHING = 0
    BOUND = 1
    """``bind_roles`` returned a Binding."""
    SOLVED = 2
    """The backend returned a BackendResult."""


@dataclass(frozen=True)
class Status:
    """The completion, solution and diagnostic of one outcome.

    Without ``code``, the error's own code applies.
    """

    completion: CompletionStatus
    solution: SolutionStatus
    code: Code | None
    severity: Severity = Severity.ERROR


@dataclass(frozen=True)
class Failure:
    """How one kind of expected error ends an attempt.

    ``after`` applies when the attempt had reached ``boundary`` before the error;
    ``before`` applies otherwise.
    """

    errors: tuple[type[BaseException], ...]
    before: Status
    boundary: Reached | None = None
    after: Status | None = None

    def status(self, reached: Reached) -> Status:
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
        Status(
            CompletionStatus.LIMITED,
            NOT_ASSESSED,
            Code.ATTEMPT_DEADLINE,
            Severity.WARNING,
        ),
    ),
    Failure(
        (ValidationError,),
        Status(FAILED, NOT_ASSESSED, Code.SPECIFICATION_INVALID),
        Reached.BOUND,
        # After binding, only a rejected candidate raises ValidationError.
        Status(FAILED, UNKNOWN, Code.NUMERICAL_REJECTION),
    ),
    Failure(
        (UnsupportedError,),
        Status(FAILED, NOT_ASSESSED, None),
        Reached.SOLVED,
        Status(FAILED, UNKNOWN, None),
    ),
    Failure(
        (UnitError,),
        Status(FAILED, NOT_ASSESSED, Code.UNSUPPORTED_CAPABILITY),
        Reached.SOLVED,
        Status(FAILED, UNKNOWN, Code.UNSUPPORTED_CAPABILITY),
    ),
    Failure(
        (BackendUnavailableError,),
        Status(FAILED, NOT_ASSESSED, Code.BACKEND_UNAVAILABLE),
    ),
    Failure(
        (NumericalError, ArithmeticError),
        Status(FAILED, UNKNOWN, Code.NUMERICAL_FAILURE),
    ),
)

EXPECTED: tuple[type[BaseException], ...] = tuple(
    error for failure in FAILURES for error in failure.errors
)


def failure(error: BaseException, reached: Reached) -> Status:
    """Return the status of an attempt that ``error`` ended after ``reached``."""
    for item in FAILURES:
        if isinstance(error, item.errors):
            return item.status(reached)
    raise LookupError(f"{type(error).__name__} is not an expected failure")


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
