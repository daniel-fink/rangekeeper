"""Finalized Run records and explicit cross-document validation."""

from .run import Run
from .validation import validate
from .._schema.records import (
    Run as RunRecord,
    Report,
    Status,
    Runtime,
    Implementation,
    Diagnostic,
    Step,
)

__all__ = [
    "Run",
    "RunRecord",
    "Report",
    "Status",
    "Runtime",
    "Implementation",
    "Diagnostic",
    "Step",
    "validate",
]

from .._schema.enums import (
    CompletionStatus,
    SolutionStatus,
    ImplementationKind,
    Severity,
    StepKind,
)

__all__ += [
    "CompletionStatus",
    "SolutionStatus",
    "ImplementationKind",
    "Severity",
    "StepKind",
]
