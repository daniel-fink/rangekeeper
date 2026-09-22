"""Optional synchronous observations; execution never depends on a UI."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Progress:
    """A phase or named-step transition, without wall time in semantic artifacts."""

    phase: str
    status: str
    step: str | None = None
    completed: int = 0
    total: int = 0


Observer = Callable[[Progress], None]


def emit(observer: Observer | None, phase: str, status: str, **fields) -> None:
    if observer is not None:
        observer(Progress(phase, status, **fields))
