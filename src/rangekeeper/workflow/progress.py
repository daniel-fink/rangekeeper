"""Optional reporting isolated from source interpretation and semantic results."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, unique
from rangekeeper.workflow.operation import Diagnostic, Severity


@unique
class ProgressPhase(Enum):
    WORKFLOW = "workflow"
    STEP = "step"
    COMPOSITION = "composition"
    CHECKS = "checks"
    EXPORT = "export"


@unique
class ProgressStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Progress:
    """One phase transition; timing is excluded from semantic artifacts."""

    phase: ProgressPhase
    status: ProgressStatus
    step: str | None = None
    completed: int = 0
    total: int = 0

    def __post_init__(self):
        if not isinstance(self.phase, ProgressPhase) or not isinstance(
            self.status, ProgressStatus
        ):
            raise TypeError("Progress requires ProgressPhase and ProgressStatus")


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
                        severity=Severity.WARNING,
                        message=f"{event.phase.value}: {type(exc).__name__}: {exc}",
                    )
                )


def emit(
    observer: Observer | None,
    phase: ProgressPhase,
    status: ProgressStatus,
    **fields,
) -> None:
    if observer is not None:
        observer(Progress(phase, status, **fields))
