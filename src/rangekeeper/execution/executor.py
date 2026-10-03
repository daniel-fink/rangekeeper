"""Sequential scalar attempts and batches over immutable revision stores."""

from datetime import datetime, timezone
import json
import time
from uuid import UUID, uuid4
from .._records import UNSET

from .._schema.records import (
    Diagnostic,
    Implementation,
    Metadata,
    Report,
    Runtime,
    Settings,
    Status,
    Step,
    CompletionStatus,
    SolutionStatus,
)
from .._schema.validation import document_version
from .._validation import bounded
from ..diagnostics import Issue, ValidationReport
from ..errors import (
    ValidationError,
    UnitError,
    ReferenceTypeError,
    IdentityConflictError,
)
from ..io.store import RecordStore
from ..model import Model
from ..run import Run, RunRecord, validate as validate_run
from ..run._validation import completion_for
from ..specification import Specification, compose
from ..specification._composition import specification_catalogue
from ..units import UnitSystem, default_units
from . import acceptance, compiler, preparation, publication, settings
from .backends import Backend, PyomoHighs
from .errors import UnsupportedProblem, NumericalError, BackendUnavailable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        documents = self._resolve(specification)
        self.store.put(specification)
        return self._execute(specification, documents)

    def _resolve(self, root: Specification) -> dict[UUID, Specification]:
        """Establish a serializable reference/case graph before executing any case."""
        documents = {root.id: root}
        pending = [root]
        while pending:
            current = pending.pop()
            if current.record.model is not None:
                model = self.store.load_model(current.record.model)
                if not isinstance(model, Model):
                    raise ReferenceTypeError(
                        "input reference did not resolve to a Model"
                    )
                if model.id != current.record.model:
                    raise IdentityConflictError(
                        "input resolver returned a different revision"
                    )
            for id in (current.record.includes or ()) + (current.record.cases or ()):
                if id in documents:
                    continue
                found = self.store.load_specification(id)
                if not isinstance(found, Specification):
                    raise ReferenceTypeError(
                        "case/include did not resolve to a Specification"
                    )
                if found.id != id:
                    raise IdentityConflictError(
                        "case/include resolver returned a different revision"
                    )
                documents[id] = found
                pending.append(found)
        # Cycles cannot form a finalized acyclic execution tree. Composition
        # conflicts and invalid numerical roles are deliberately left for leaves.
        data = {str(id): spec.to_data() for id, spec in documents.items()}
        bounded(
            [],
            lambda: specification_catalogue(
                root.to_data(), data, document_version("Specification")
            ),
        ).raise_if_invalid()

        def check_pins(current: Specification, pins: tuple[UUID, ...] = ()) -> None:
            if current.record.cases:
                pins += (
                    (current.record.model,) if current.record.model is not None else ()
                )
                for id in current.record.cases:
                    check_pins(documents[id], pins)
            else:
                try:
                    view = compose(current, resolver=self.store)
                except ValidationError:
                    return  # the leaf will record its conflicting composition
                if view.model_id is not None and any(
                    pin != view.model_id for pin in pins
                ):
                    raise ValidationError(
                        ValidationReport(
                            (
                                Issue(
                                    "batch.model",
                                    "batch input Model assertion mismatch",
                                    current.id,
                                ),
                            )
                        )
                    )

        check_pins(root)
        return documents

    def _execute(
        self, specification: Specification, documents: dict[UUID, Specification]
    ) -> Run:
        if specification.record.cases:
            children = tuple(
                self._execute(documents[id], documents)
                for id in specification.record.cases
            )
            outputs = tuple(
                dict.fromkeys(
                    id for child in children for id in child.record.outputs or ()
                )
            )
            completion = completion_for([child.to_data() for child in children])
            run = Run(
                RunRecord(
                    metadata=Metadata(
                        id=uuid4(), schema_version=document_version("Run")
                    ),
                    specification=specification.id,
                    spawns=tuple(child.id for child in children),
                    outputs=outputs,
                    report=Report(
                        status=Status(completion=completion, solution="not_applicable"),
                        diagnostics=(
                            Diagnostic(
                                severity=(
                                    "info" if completion == "completed" else "warning"
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
        return self._scalar(specification)

    def _scalar(self, specification: Specification) -> Run:
        run_id, started, clock = uuid4(), _now(), time.monotonic()
        findings: list[Diagnostic] = []
        trace: list[Step] = []
        implementations = [
            Implementation(kind="compiler", name="rangekeeper.scalar", version="1")
        ]
        limits = None
        prepared = None
        result = None
        output = None
        completion: CompletionStatus = "failed"
        solution: SolutionStatus = "not_assessed"
        try:
            view = compose(specification, resolver=self.store)
            limits, adjustments = settings.resolve(view.requirements.settings)
            findings.extend(adjustments)
            prepared = preparation.prepare(
                specification, resolver=self.store, units=self.units
            )
            trace.append(
                Step(
                    kind="validation",
                    at=_now(),
                    document=specification.id,
                    message="Validated additive composition, exact Model pin, scalar roles and recorded units.",
                )
            )
            problem = compiler.compile(prepared)
            trace.append(
                Step(
                    kind="formulation",
                    at=_now(),
                    message=f"Compiled {len(problem.rows)} affine equality/bound rows after explicit assignments.",
                )
            )
            if view.requirements.estimates:
                findings.append(
                    Diagnostic(
                        severity="info",
                        code="estimates_unused",
                        message="Simplex feasibility uses no initial primal estimate; estimates are not assignments.",
                    )
                )
            findings.append(
                Diagnostic(
                    severity="info",
                    code="solver_scaling",
                    message=json.dumps(
                        [
                            {
                                "constraint": str(row.assertion.constraint.id),
                                "divisor": row.scale,
                                "residual_units": row.residual.units,
                            }
                            for row in problem.rows
                        ]
                    ),
                )
            )
            result = self.backend.solve(
                problem,
                limits=limits,
                remaining=limits.time_limit - (time.monotonic() - clock),
            )
            implementations.extend(result.implementations)
            findings.append(
                Diagnostic(
                    severity="info",
                    code="solver_termination",
                    message=json.dumps(
                        {"termination": result.termination, **result.evidence},
                        allow_nan=False,
                    ),
                )
            )
            trace.append(
                Step(
                    kind="solve",
                    at=_now(),
                    message=f"Backend returned {result.termination}; independent acceptance follows when a candidate exists.",
                )
            )
            limited = result.termination in {
                "worker_deadline",
                "maxTimeLimit",
                "iterationLimit",
                "objectiveLimit",
            }
            completion = "limited" if limited else "completed"
            solution = "unknown"
            if result.termination == "provenInfeasible":
                solution = "infeasible"
            elif result.termination in {"error", "interrupted"}:
                completion = "failed"
            elif result.candidate is not None:
                candidate = publication.candidate(
                    prepared, result.candidate, run_id=run_id
                )
                checked = acceptance.check(
                    prepared, candidate, tolerances=self.tolerances
                )
                implementations.append(
                    Implementation(
                        kind="evaluator",
                        name="rangekeeper.scalar.original_expressions",
                        version="1",
                    )
                )
                findings.extend(checked.diagnostics)
                if checked.accepted:
                    output, solution = candidate, "feasible"
                    findings.append(
                        Diagnostic(
                            severity="info",
                            code="feasible_candidate",
                            message="Original expressions, assignments and bounds accepted. No uniqueness or optimization claim is made.",
                        )
                    )
                    rank, count = result.evidence.get(
                        "equality_rank"
                    ), result.evidence.get("unknown_count")
                    if (
                        isinstance(rank, int)
                        and isinstance(count, int)
                        and rank < count
                    ):
                        findings.append(
                            Diagnostic(
                                severity="warning",
                                code=(
                                    "underdetermined"
                                    if not result.evidence.get("has_bounds")
                                    else "uniqueness_not_assessed"
                                ),
                                message=f"Numerical equality rank {rank} for {count} unknowns (NumPy SVD default threshold). "
                                "Bounds may restrict freedom; this is one accepted candidate, not a uniqueness proof.",
                            )
                        )
                else:
                    completion = "failed"
                    findings.append(
                        Diagnostic(
                            severity="error",
                            code="numerical_rejection",
                            message="Serialized candidate failed independent acceptance; no output was published.",
                        )
                    )
        except ValidationError as error:
            completion, solution = "failed", (
                "not_assessed" if prepared is None else "unknown"
            )
            findings.append(
                Diagnostic(
                    severity="error",
                    code=(
                        "specification_invalid"
                        if prepared is None
                        else "numerical_rejection"
                    ),
                    message=str(error),
                )
            )
        except (UnsupportedProblem, UnitError) as error:
            completion, solution = "failed", (
                "not_assessed" if result is None else "unknown"
            )
            findings.append(
                Diagnostic(
                    severity="error",
                    code="unsupported_capability",
                    message=str(error),
                    document=(
                        error.document
                        if isinstance(error, UnsupportedProblem) and error.document
                        else UNSET
                    ),
                    target=(
                        error.target
                        if isinstance(error, UnsupportedProblem) and error.target
                        else UNSET
                    ),
                )
            )
        except BackendUnavailable as error:
            findings.append(
                Diagnostic(
                    severity="error", code="backend_unavailable", message=str(error)
                )
            )
        except (NumericalError, ArithmeticError) as error:
            completion, solution = "failed", "unknown"
            findings.append(
                Diagnostic(
                    severity="error", code="numerical_failure", message=str(error)
                )
            )

        # No returned worker evidence means no claim that its iteration setting or
        # solver implementation actually ran. The parent deadline still applies.
        effective = (
            limits.record()
            if limits and result and result.termination != "worker_deadline"
            else Settings(time_limit=limits.time_limit) if limits else Settings()
        )
        if result is None or result.termination == "worker_deadline":
            findings.append(
                Diagnostic(
                    severity="warning",
                    code="settings_adjusted",
                    message="relative_tolerance and iteration_limit were not applied by a completed solver invocation; "
                    "time_limit applies to the parent attempt budget when preparation established it. No infeasibility follows.",
                )
            )
        if output is not None:
            trace.append(
                Step(
                    kind="publication",
                    at=_now(),
                    document=output.id,
                    message="Accepted serialized immutable Model; store output before finalized Run.",
                )
            )
        findings.append(
            Diagnostic(
                severity="info",
                code="attempt_timing",
                message=f"Elapsed monotonic time before persistence: {time.monotonic() - clock:.9f} seconds.",
            )
        )
        run = Run(
            RunRecord(
                metadata=Metadata(id=run_id, schema_version=document_version("Run")),
                specification=specification.id,
                outputs=() if output is None else (output.id,),
                report=Report(
                    status=Status(completion=completion, solution=solution),
                    runtime=Runtime(
                        started_at=started,
                        finished_at=_now(),
                        implementations=tuple(implementations),
                        settings=effective,
                    ),
                    diagnostics=tuple(findings),
                    trace=tuple(trace),
                ),
            )
        )
        resolver = (
            self.store
            if output is None
            else publication.CandidateResolver(output, self.store)
        )
        validate_run(run, resolver=resolver, units=self.units).raise_if_invalid()
        if output is not None:
            self.store.put(output)
        self.store.put(run)
        return run
