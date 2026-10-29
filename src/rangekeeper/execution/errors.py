"""Expected execution failures, separate from document and storage errors."""

from typing import Any, Unpack

from rangekeeper.execution.status import Status
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AttemptDeadlineError,
    BackendUnavailableError,
    ErrorFields,
    NumericalError,
    RangekeeperError,
    UnsupportedError,
)


class OutcomeError(RangekeeperError, ValueError):
    """An Outcome's status has no more specific error.

    ``Outcome.raise_for_status()`` raises it for an underdetermined or
    infeasible solve, and for a limit or failure that no other error names.
    ``status`` is the Outcome's ``Status``; ``code`` is the code of the
    diagnostic that gives the reason, by default ``solver_termination``.
    ``document_id`` and ``targets`` locate it when they are known.
    """

    code = Code.SOLVER_TERMINATION

    def __init__(
        self,
        message: str,
        *,
        status: Status,
        **fields: Unpack[ErrorFields],
    ) -> None:
        super().__init__(message, **fields)
        self.status = Status(status)

    def _fields(self) -> dict[str, Any]:
        return {**super()._fields(), "status": self.status}


__all__ = [
    "AttemptDeadlineError",
    "BackendUnavailableError",
    "NumericalError",
    "OutcomeError",
    "UnsupportedError",
]
