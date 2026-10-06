"""Optional reporting isolated from source interpretation and semantic results."""

from collections.abc import Callable
from dataclasses import dataclass
from rangekeeper.operation import Diagnostic, IssueSeverity


@dataclass(frozen=True, slots=True)
class Progress:
    """One phase transition; timing is excluded from semantic artifacts."""

    phase: str
    status: str
    step: str | None = None
    completed: int = 0
    total: int = 0


Observer = Callable[[Progress], None]


class Reporter:
    """Contain ordinary observer errors as separate reporting diagnostics.

    Observers receive immutable events, never a Model or execution storage. A
    KeyboardInterrupt still interrupts the caller's operation.
    """

    def __init__(self, observer: Observer | None):
        self.observer = observer
        self.diagnostics: list[Diagnostic] = []

    def __call__(self, event: Progress) -> None:
        if self.observer is not None:
            try:
                self.observer(event)
            except Exception as exc:
                self.diagnostics.append(
                    Diagnostic(
                        code="progress_observer_failed",
                        severity=IssueSeverity.WARNING,
                        message=f"{event.phase}: {type(exc).__name__}: {exc}",
                    )
                )


def emit(observer: Observer | None, phase: str, status: str, **fields) -> None:
    if observer is not None:
        observer(Progress(phase, status, **fields))
