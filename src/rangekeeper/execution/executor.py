"""Sequential scalar attempts and batches over immutable revision stores."""

from uuid import uuid4

from rangekeeper.execution.attempt import Attempt
from rangekeeper.execution.backends import registry
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.planning import Cases, resolve_cases
from rangekeeper.run import Run, RunRecord, Severity, SolutionStatus
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
from rangekeeper.shared.store import RecordStore
from rangekeeper.specification import Specification


class Executor:
    """Execute scalar feasibility problems, independently accept, then persist results.

    ``store`` supplies exact immutable revisions and receives finalized documents.
    The root Specification is stored after reference-graph preflight. Each batch
    case has a fresh Run even when it fails; repeated paths are separate attempts.
    Missing references, invalid batch graphs, storage errors and programming errors
    raise to the caller. Expected formulation/numerical failures become Run evidence.
    ``config`` gives the backend, unit system, limits, tolerances and backend
    options; without it, the defaults of ExecutionConfig apply. Run evidence
    records the backend's registered name and fingerprint.
    No commit, network access, graph migration or source-workflow execution occurs.
    """

    def __init__(
        self,
        store: RecordStore,
        *,
        config: ExecutionConfig | None = None,
    ) -> None:
        self.store = store
        self.config = ExecutionConfig() if config is None else config
        backend = self.config.backend
        self.backend = registry.get(backend) if isinstance(backend, str) else backend

    def execute(self, specification: Specification) -> Run:
        """Persist one finalized execution tree; return its root immutable Run.

        Outputs are stored before their Run; there is no multi-document transaction.
        A storage error can leave complete accepted outputs or completed child Runs.
        Caller-owned input records never change. A finalized Run certifies only the
        documented scalar slice and independent acceptance, not uniqueness/optimality.
        """
        if not isinstance(specification, Specification):
            raise TypeError("specification must be a Specification")
        cases = resolve_cases(specification, resolver=self.store)
        self.store.put(specification)
        return self._execute(specification, cases)

    def _execute(self, specification: Specification, cases: Cases) -> Run:
        if specification.record.cases:
            children = tuple(
                self._execute(cases.documents[id], cases)
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
                                code=Code.BATCH_ACCOUNTING.value,
                                message=f"Sequential batch accounted for all {len(children)} direct cases; outputs are their unique accepted union.",
                            ),
                        ),
                    ),
                )
            )
            self.store.put(run)
            return run
        run, output = Attempt(
            self.config,
            self.backend,
            specification,
            cases.compositions[specification.id],
            resolver=cases,
        ).execute()
        if output is not None:
            self.store.put(output)
        self.store.put(run)
        return run
