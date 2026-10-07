"""Sequential scalar attempts and batches over immutable revision stores."""

from rangekeeper.run import Severity
from rangekeeper.run import SolutionStatus

from uuid import UUID, uuid4

from .._schema.records import Diagnostic, Metadata, Report, Status, CompletionStatus
from .._schema.validation import document_version
from ..errors import ValidationError
from ..io.store import RecordStore
from ..run import Run, RunRecord
from ..run.report import completion_for
from ..specification import Composition, Specification
from ..units import UnitSystem, default_units
from . import acceptance
from .backends import Backend, PyomoHighs


from .attempt import Attempt
from .planning import Plan


class Executor:
    """Execute scalar feasibility problems, independently accept, then persist results.

    ``store`` supplies exact immutable revisions and receives finalized documents.
    The root Specification is stored after reference-graph preflight. Each batch
    case has a fresh Run even when it fails; repeated paths are separate attempts.
    Missing references, invalid batch graphs, storage errors and programming errors
    raise to the caller. Expected formulation/numerical failures become Run evidence.
    No commit, network access, graph migration or source-workflow execution occurs.
    """

    def __init__(
        self,
        store: RecordStore,
        *,
        backend: Backend | None = None,
        units: UnitSystem = default_units,
        tolerances: acceptance.Tolerances = acceptance.Tolerances(),
    ) -> None:
        self.store = store
        self.backend = backend if backend is not None else PyomoHighs()
        self.units = units
        self.tolerances = tolerances

    def execute(self, specification: Specification) -> Run:
        """Persist one finalized execution tree; return its root immutable Run.

        Outputs are stored before their Run; there is no multi-document transaction.
        A storage error can leave complete accepted outputs or completed child Runs.
        Caller-owned input records never change. A finalized Run certifies only the
        documented scalar slice and independent acceptance, not uniqueness/optimality.
        """
        if not isinstance(specification, Specification):
            raise TypeError("specification must be a Specification")
        plan = Plan(self.store)
        documents, compositions = plan.resolve(specification)
        self.store.put(specification)
        return self._execute(specification, documents, compositions, plan)

    def _execute(
        self,
        specification: Specification,
        documents: dict[UUID, Specification],
        compositions: dict[UUID, Composition | ValidationError],
        plan: Plan,
    ) -> Run:
        if specification.record.cases:
            children = tuple(
                self._execute(documents[id], documents, compositions, plan)
                for id in specification.record.cases
            )
            outputs = tuple(
                dict.fromkeys(
                    id for child in children for id in child.record.outputs or ()
                )
            )
            completion = completion_for(
                child.report.status.completion for child in children
            )
            run = Run(
                RunRecord(
                    metadata=Metadata(
                        id=uuid4(), schema_version=document_version("Run")
                    ),
                    specification=specification.id,
                    spawns=tuple(child.id for child in children),
                    outputs=outputs,
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
                                code="batch_accounting",
                                message=f"Sequential batch accounted for all {len(children)} direct cases; outputs are their unique accepted union.",
                            ),
                        ),
                    ),
                )
            )
            self.store.put(run)
            return run
        return Attempt(
            self.store,
            self.backend,
            self.units,
            self.tolerances,
            specification,
            compositions[specification.id],
            resolver=plan,
        ).execute()
