"""Expected execution failures, separate from document and storage errors."""

from uuid import UUID

from rangekeeper.shared.codes import Code


class UnsupportedProblem(ValueError):
    """The declared problem falls outside the supported scalar capability."""

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


class NumericalError(ValueError):
    """Arithmetic or a backend candidate cannot support numerical acceptance."""


class BackendUnavailable(RuntimeError):
    """The optional, pinned execution backend cannot be loaded."""


class AttemptDeadline(RuntimeError):
    """The attempt budget expired at a preparation or compilation checkpoint."""
