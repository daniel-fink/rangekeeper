"""Bounded finalized-Run checks; synthetic fixtures are not solver evidence."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .run import Run
    from ..references import DocumentResolver

from .._records import Record
from .._schema.validation import document_version
from .._validation import bounded, checked
from ..diagnostics import Issue, ValidationReport
from ._validation import validate_run


def validate_records(
    run: Record | Mapping[str, object],
    *,
    runs: Mapping[str, Record | Mapping[str, object]],
    specifications: Mapping[str, Record | Mapping[str, object]],
    models: Mapping[str, Record | Mapping[str, object]],
) -> ValidationReport:
    """Check the reachable tree against explicit revision-keyed catalogues."""
    issues: list[Issue] = []
    root = checked("Run", run, "", issues)
    run_data = {
        key: checked("Run", value, f"/runs/{key}", issues)
        for key, value in runs.items()
    }
    spec_data = {
        key: checked("Specification", value, f"/specifications/{key}", issues)
        for key, value in specifications.items()
    }
    model_data = {
        key: checked("Model", value, f"/models/{key}", issues)
        for key, value in models.items()
    }
    return bounded(
        issues,
        lambda: validate_run(
            root,
            run_data,
            spec_data,
            model_data,
            document_version("Run"),
            document_version("Specification"),
            document_version("Model"),
        ),
        document=root,
    )


def validate(run: "Run", *, resolver: "DocumentResolver") -> ValidationReport:
    """Check a finalized tree and published outputs against exact resolved revisions.

    The supplied Run need not be stored yet. Resolution performs only the reads
    provided by the resolver. References must resolve even for failed attempts;
    incomplete or mathematically invalid Specifications may support not_assessed
    outcomes with the required diagnostic. No solver or scheduler is invoked.
    """
    from .run import Run
    from ._resolve import collect_documents
    from ..errors import (
        MissingReferenceError,
        ReferenceTypeError,
        IdentityConflictError,
    )

    if not isinstance(run, Run):
        raise TypeError("run must be a Run; use validate_records for raw catalogues")
    try:
        runs, specifications, models = collect_documents(run, resolver)
        return validate_records(
            run.record, runs=runs, specifications=specifications, models=models
        )
    except (MissingReferenceError, ReferenceTypeError, IdentityConflictError) as error:
        code = (
            "reference.missing"
            if isinstance(error, MissingReferenceError)
            else (
                "reference.kind"
                if isinstance(error, ReferenceTypeError)
                else "reference.identity"
            )
        )
        return ValidationReport((Issue(code, str(error), run.id),))
