"""Stage 8: assemble the finalized Run of one leaf case; nothing is stored here."""

from uuid import UUID

from rangekeeper.execution.publication import CandidateResolver
from rangekeeper.model import Model
from rangekeeper.quantity import UnitSystem
from rangekeeper.run import Run, RunRecord
from rangekeeper.run import validate as validate_run
from rangekeeper.schema.records import Metadata, Report
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.specification import Specification


def assemble(
    specification: Specification,
    report: Report,
    *,
    id: UUID,
    output: Model | None,
    resolver: DocumentResolver,
    units: UnitSystem | None = None,
) -> Run:
    """Make the finalized Run of one leaf case and validate it once.

    The Run validates against ``resolver`` with ``output`` laid over it, so
    the output need not be stored first. Without ``units``, validation uses
    the unit system of the input Model. Raise ValidationError for an invalid
    Run.
    """
    run = Run(
        RunRecord(
            metadata=Metadata(id=id, schema_version=document_version("Run")),
            specification=specification.id,
            outputs=() if output is None else (output.id,),
            report=report,
        )
    )
    overlay = resolver if output is None else CandidateResolver(output, resolver)
    validate_run(run, resolver=overlay, units=units).raise_if_invalid()
    return run
