"""Expected execution failures, separate from document and storage errors."""

from enum import StrEnum
from uuid import UUID

from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AttemptDeadlineError,
    BackendUnavailableError,
    NumericalError,
    RangekeeperError,
    UnsupportedError,
)


class OutcomeError(RangekeeperError, RuntimeError):
    """An Outcome's status has no more specific error.

    ``Outcome.raise_for_status()`` raises it for an underdetermined or
    infeasible solve, and for a limit or failure that no other error names.
    ``status`` is the Outcome's ``Status``; ``code`` is the code of the
    diagnostic that gives the reason. ``document`` and ``target`` locate it
    when they are known.
    """

    def __init__(
        self,
        message: str,
        *,
        status: StrEnum,
        code: Code | None = None,
        document: UUID | None = None,
        target: UUID | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = Code.SOLVER_TERMINATION if code is None else Code(code)
        self.document = document
        self.target = target


__all__ = [
    "AttemptDeadlineError",
    "BackendUnavailableError",
    "NumericalError",
    "OutcomeError",
    "UnsupportedError",
]
