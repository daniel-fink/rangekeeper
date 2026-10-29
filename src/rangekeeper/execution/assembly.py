"""Stage 8: assemble the Outcome of a leaf case or a batch; nothing is stored here."""

from collections.abc import Iterable, Sequence
from uuid import UUID, uuid4

from rangekeeper.execution.outcome import Outcome
from rangekeeper.model import Model
from rangekeeper.quantity import UnitSystem
from rangekeeper.run import Run, RunRecord, Severity, SolutionStatus
from rangekeeper.run import validate as validate_run
from rangekeeper.run.report import completion_for
from rangekeeper.schema.records import (
    CompletionStatus,
    Diagnostic,
    Metadata,
    Report,
    Status,
)
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.codes import Code
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.specification import Specification


class Overlay:
    """Resolve unstored outputs and Runs first, then read from ``resolver``.

    Final Run validation uses an Overlay, so that nothing is stored before the
    Run is valid.
    """

    def __init__(
        self,
        resolver: DocumentResolver,
        *,
        models: Iterable[Model] = (),
        runs: Iterable[Run] = (),
    ) -> None:
        self.resolver = resolver
        self.models = {model.id: model for model in models}
        self.runs = {run.id: run for run in runs}

    def load_model(self, id: UUID) -> Model:
        """Return an overlaid Model, else load it from the resolver."""
        found = self.models.get(id)
        return self.resolver.load_model(id) if found is None else found

    def load_specification(self, id: UUID) -> Specification:
        """Load a Specification from the resolver."""
        return self.resolver.load_specification(id)

    def load_run(self, id: UUID) -> Run:
        """Return an overlaid Run, else load it from the resolver."""
        found = self.runs.get(id)
        return self.resolver.load_run(id) if found is None else found


def assemble(
    specification: Specification,
    report: Report,
    *,
    id: UUID,
    output: Model | None,
    resolver: DocumentResolver,
    units: UnitSystem | None = None,
    validate: bool = True,
) -> Outcome:
    """Make the Outcome of one leaf case, with its finalized Run.

    With ``validate``, the Run is validated once against ``resolver`` with
    ``output`` laid over it, so the output need not be stored first, and an
    invalid Run raises ValidationError. Pass ``validate=False`` only when a
    later commit point validates the Run, such as ``RecordStore.put``.
    Without ``units``, validation uses the unit system of the input Model.
    """
    run = Run(
        RunRecord(
            metadata=Metadata(id=id, schema_version=document_version("Run")),
            specification=specification.id,
            outputs=() if output is None else (output.id,),
            report=report,
        )
    )
    outputs = () if output is None else (output,)
    if validate:
        overlay = Overlay(resolver, models=outputs)
        validate_run(run, resolver=overlay, units=units).raise_if_invalid()
    return Outcome(run, outputs)


def assemble_batch(
    specification: Specification,
    cases: Sequence[Outcome],
    *,
    resolver: DocumentResolver,
    validate: bool = True,
) -> Outcome:
    """Make the Outcome of a batch from the Outcomes of its direct cases.

    The batch Run spawns each case Run. Its outputs are the unique union of
    the case outputs, and its completion follows from theirs. ``validate``
    has the same meaning as for ``assemble``; the overlay holds every Run and
    output of the cases.
    """
    outputs: dict[UUID, Model] = {}
    for case in cases:
        for model in case.outputs:
            outputs.setdefault(model.id, model)
    completion = completion_for(case.run.report.status.completion for case in cases)
    run = Run(
        RunRecord(
            metadata=Metadata(id=uuid4(), schema_version=document_version("Run")),
            specification=specification.id,
            spawns=tuple(case.run.id for case in cases),
            outputs=tuple(outputs),
            report=Report(
                status=Status(
                    completion=completion,
                    solution=SolutionStatus.NOT_APPLICABLE,
                ),
                diagnostics=(
                    Diagnostic(
                        severity=(
                            Severity.INFO
                            if completion is CompletionStatus.COMPLETED
                            else Severity.WARNING
                        ),
                        code=Code.BATCH_ACCOUNTING.value,
                        message=f"Sequential batch accounted for all {len(cases)} direct cases; outputs are their unique accepted union.",
                    ),
                ),
            ),
        )
    )
    if validate:
        tree = [item for case in cases for item in case.walk()]
        overlay = Overlay(
            resolver,
            models=(model for item in tree for model in item.outputs),
            runs=(item.run for item in tree),
        )
        validate_run(run, resolver=overlay).raise_if_invalid()
    return Outcome(run, tuple(outputs.values()), tuple(cases))
