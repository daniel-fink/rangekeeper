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
from ..units import UnitSystem, default_units
from .._schema.records import Quantity
from ..errors import UnitError


def validate_records(
    run: Record | Mapping[str, object],
    *,
    runs: Mapping[str, Record | Mapping[str, object]],
    specifications: Mapping[str, Record | Mapping[str, object]],
    models: Mapping[str, Record | Mapping[str, object]],
    units: UnitSystem | None = None,
) -> ValidationReport:
    """Check a revision-keyed tree; opt into assignment conversion with ``units``.

    Raw conformance defaults remain strict. The public facade validator supplies
    its UnitSystem so physically equivalent assigned/output quantities can match.
    """

    def compatible(left, right):
        assert units is not None
        try:
            return units.compatible(left, right)
        except UnitError:
            # An invalid supplied unit makes the Specification invalid. A failed
            # not_assessed Run may still record that unsuccessful attempt.
            return False

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
            units_compatible=None if units is None else compatible,
            quantities_equal=(
                None
                if units is None
                else lambda actual, requested: actual
                == units.convert(
                    Quantity.from_data(requested), to=actual["units"]
                ).to_data()
            ),
        ),
        document=root,
    )


def validate(
    run: "Run", *, resolver: "DocumentResolver", units: UnitSystem = default_units
) -> ValidationReport:
    """Check a finalized tree and published outputs against exact resolved revisions.

    The supplied Run need not be stored yet. Resolution performs only the reads
    provided by the resolver. References must resolve even for failed attempts;
    incomplete or mathematically invalid Specifications may support not_assessed
    outcomes with the required diagnostic. No solver or scheduler is invoked.
    Assignments are compared after explicit conversion to output Measure units;
    this does not evaluate equations or certify a solver's numerical claims.
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
            run.record,
            runs=runs,
            specifications=specifications,
            models=models,
            units=units,
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
