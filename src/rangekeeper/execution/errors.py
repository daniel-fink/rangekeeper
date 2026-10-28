"""Expected execution failures, separate from document and storage errors."""

from rangekeeper.shared.errors import (
    AttemptDeadlineError,
    BackendUnavailableError,
    NumericalError,
    UnsupportedError,
)

__all__ = [
    "AttemptDeadlineError",
    "BackendUnavailableError",
    "NumericalError",
    "UnsupportedError",
]
