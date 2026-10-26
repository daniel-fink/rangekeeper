"""Finalized Run records and explicit cross-document validation."""

from rangekeeper.run.run import Run
from rangekeeper.run.validation import validate
from rangekeeper.schema.records import (
    Diagnostic,
    Implementation,
    Report,
    Runtime,
    Status,
    Step,
)
from rangekeeper.schema.records import (
    Run as RunRecord,
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

from rangekeeper.schema.enums import (
    CompletionStatus,
    ImplementationKind,
    Severity,
    SolutionStatus,
    StepKind,
)

__all__ += [
    "CompletionStatus",
    "SolutionStatus",
    "ImplementationKind",
    "Severity",
    "StepKind",
]
