"""Stage 8: assemble the Outcome of a leaf case or a batch; nothing is stored here."""

from collections.abc import Iterable, Sequence
from uuid import UUID, uuid4

from rangekeeper.execution.outcome import Outcome
from rangekeeper.market.paths import Paths
from rangekeeper.model import Model
from rangekeeper.run import Run, RunRecord, Severity, SolutionStatus
from rangekeeper.run.documents import Documents
from rangekeeper.run.report import completion_for
from rangekeeper.schema.records import (
    CompletionStatus,
    Diagnostic,
    Metadata,
    Report,
    RunStatus,
)
from rangekeeper.schema.runtime import UNSET
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.codes import Code
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.specification import Specification


class Overlay:
    """A resolver that returns unstored outputs and Runs, then reads ``resolver``.

    Validate the Run of an Outcome before anything is stored with
    ``rk.run.validate(run=outcome.run, resolver=Overlay(resolver=store,
    models=outcome.outputs))``. For a batch, give every output and case Run of
    ``outcome.walk()``. ``execute`` validates its Runs this way.
    """

    __slots__ = ("_documents",)
    _documents: Documents

    def __init__(
        self,
        *,
        resolver: DocumentResolver,
        models: Iterable[Model] = (),
        runs: Iterable[Run] = (),
    ) -> None:
        self._documents = Documents((*models, *runs), fallback=resolver)

    def load_model(self, id: UUID) -> Model:
        """Return an overlaid Model, else load it from the resolver."""
        return self._documents.load_model(id)

    def load_specification(self, id: UUID) -> Specification:
        """Load a Specification from the resolver."""
        return self._documents.load_specification(id)

    def load_run(self, id: UUID) -> Run:
        """Return an overlaid Run, else load it from the resolver."""
        return self._documents.load_run(id)

    def load_paths(self, id: UUID) -> Paths:
        """Load market paths from the resolver."""
        return self._documents.load_paths(id)


def assemble(
    *,
    specification: Specification,
    report: Report,
    id: UUID,
    output: Model | None,
) -> Outcome:
    """Make the Outcome of one leaf case, with its finalized Run.

    Nothing is resolved or validated. Validate the Run as its own step, with
    ``rk.run.validate(run=outcome.run, resolver=Overlay(resolver=resolver,
    models=outcome.outputs))``, or let a store validate it on ``put``.
    """
    path = specification.record.path
    run = Run(
        RunRecord(
            metadata=Metadata(id=id, schema_version=document_version("Run")),
            specification=specification.id,
            outputs=() if output is None else (output.id,),
            paths=UNSET if path is None else path.paths,
            report=report,
        )
    )
    return Outcome(run=run, outputs=() if output is None else (output,))


def assemble_batch(
    *,
    specification: Specification,
    cases: Sequence[Outcome],
) -> Outcome:
    """Make the Outcome of a batch from the Outcomes of its direct cases.

    The batch Run spawns each case Run. Its outputs are the unique union of
    the case outputs, and its completion follows from theirs. Nothing is
    resolved or validated, as for ``assemble``; an Overlay for validation
    holds every Run and output of the cases.
    """
    outputs: dict[UUID, Model] = {}
    for case in cases:
        for model in case.outputs:
            outputs.setdefault(model.id, model)
    completion = completion_for(case.run.report.status.completion for case in cases)
    # A batch pins the Paths that each of its cases takes its path from.
    pinned = {case.run.paths for case in cases}
    paths = pinned.pop() if len(pinned) == 1 else None
    run = Run(
        RunRecord(
            metadata=Metadata(id=uuid4(), schema_version=document_version("Run")),
            specification=specification.id,
            spawns=tuple(case.run.id for case in cases),
            outputs=tuple(outputs),
            paths=UNSET if paths is None else paths,
            report=Report(
                status=RunStatus(
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
    return Outcome(run=run, outputs=tuple(outputs.values()), cases=tuple(cases))
