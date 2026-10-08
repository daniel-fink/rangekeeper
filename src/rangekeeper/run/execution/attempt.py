"""Sequential scalar attempts and batches over immutable revision stores."""

from rangekeeper.run import ImplementationKind
from rangekeeper.run import StepKind

from datetime import datetime, timezone
import json
import time
from uuid import UUID, uuid4
from rangekeeper.schema.runtime import UNSET, Unset

from rangekeeper.schema.records import (
    Diagnostic,
    Severity,
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
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.errors import ValidationError, UnitError
from rangekeeper.io.store import RecordStore
from rangekeeper.model import Model
from rangekeeper.run import Run, RunRecord, validate as validate_run
from rangekeeper.specification import Composition, Specification
from rangekeeper.shared.units import UnitSystem
from rangekeeper.run.execution import (
    acceptance,
    compiler,
    preparation,
    publication,
    settings,
)
from rangekeeper.run.execution.implementation import fingerprint
from rangekeeper.run.execution.backends import Backend
from rangekeeper.run.execution.backends.base import Result
from rangekeeper.run.execution.errors import (
    UnsupportedProblem,
    NumericalError,
    BackendUnavailable,
    AttemptDeadline,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Attempt:
    """One scalar attempt owns its deadline, candidate and report evidence.

    Preparation, backend solving, and independent acceptance stay separate.
    Only finish persists records; expected failures still produce a finalized Run.
    """

    def __init__(
        self,
        store: RecordStore,
        backend: Backend,
        units: UnitSystem,
        tolerances: acceptance.Tolerances,
        specification: Specification,
        view: Composition | ValidationError,
        *,
        resolver=None,
    ) -> None:
        self.store, self.backend, self.units, self.tolerances = (
            store,
            backend,
            units,
            tolerances,
        )
        self.specification, self.view = specification, view
        self.resolver = resolver if resolver is not None else store
        self.run_id, self.started, self.clock = uuid4(), _now(), time.monotonic()
        self.findings: list[Diagnostic] = []
        self.trace: list[Step] = []
        self.implementations = [
            Implementation(
                kind=ImplementationKind.COMPILER,
                name="rangekeeper.scalar",
                version=fingerprint("compiler"),
            )
        ]
        self.limits: settings.Limits | None = None
        self.prepared: preparation.Prepared | None = None
        self.result: Result | None = None
        self.output: Model | None = None
        self.completion: CompletionStatus = CompletionStatus.FAILED
        self.solution: SolutionStatus = SolutionStatus.NOT_ASSESSED

    def diagnose(
        self,
        code: str,
        message: str,
        *,
        severity: Severity = Severity.INFO,
        document: UUID | Unset = UNSET,
        target: UUID | Unset = UNSET,
    ) -> None:
        """Attach an outcome or adjustment to this attempt's report."""
        self.findings.append(
            Diagnostic(
                severity=severity,
                code=code,
                message=message,
                document=document,
                target=target,
            )
        )

    def checkpoint(self) -> None:
        if (
            self.limits is not None
            and time.monotonic() - self.clock >= self.limits.time_limit
        ):
            raise AttemptDeadline(
                "execution deadline reached during preparation or compilation"
            )

    def execute(self) -> Run:
        """Run the bounded phases and account for each expected failure."""
        try:
            problem = self.prepare()
            result = self.solve(problem)
            self.accept(result)
        except AttemptDeadline as error:
            self.completion, self.solution = (
                CompletionStatus.LIMITED,
                SolutionStatus.NOT_ASSESSED,
            )
            self.diagnose("attempt_deadline", str(error), severity=Severity.WARNING)
        except ValidationError as error:
            self.completion, self.solution = CompletionStatus.FAILED, (
                SolutionStatus.NOT_ASSESSED
                if self.prepared is None
                else SolutionStatus.UNKNOWN
            )
            self.diagnose(
                (
                    "specification_invalid"
                    if self.prepared is None
                    else "numerical_rejection"
                ),
                str(error),
                severity=Severity.ERROR,
            )
        except (UnsupportedProblem, UnitError) as error:
            self.completion, self.solution = CompletionStatus.FAILED, (
                SolutionStatus.NOT_ASSESSED
                if self.result is None
                else SolutionStatus.UNKNOWN
            )
            self.diagnose(
                "unsupported_capability",
                str(error),
                severity=Severity.ERROR,
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
        except BackendUnavailable as error:
            self.diagnose("backend_unavailable", str(error), severity=Severity.ERROR)
        except (NumericalError, ArithmeticError) as error:
            self.completion, self.solution = (
                CompletionStatus.FAILED,
                SolutionStatus.UNKNOWN,
            )
            self.diagnose("numerical_failure", str(error), severity=Severity.ERROR)

        return self.finish()

    def prepare(self) -> compiler.Compiled:
        """Validate roles and compile within the same parent deadline."""
        if isinstance(self.view, ValidationError):
            raise self.view
        self.limits, adjustments = settings.resolve(self.view.requirements.settings)
        self.findings.extend(adjustments)
        self.prepared = preparation.prepare(
            self.view,
            resolver=self.resolver,
            units=self.units,
            checkpoint=self.checkpoint,
        )
        self.checkpoint()
        self.trace.append(
            Step(
                kind=StepKind.VALIDATION,
                at=_now(),
                document=self.specification.id,
                message="Validated additive composition, exact Model pin, scalar roles and recorded units.",
            )
        )
        if len(self.prepared.references) > self.limits.symbol_limit:
            raise UnsupportedProblem("expanded symbol limit exceeded")
        problem = compiler.compile(
            self.prepared,
            checkpoint=self.checkpoint,
            constraint_limit=self.limits.constraint_limit,
        )
        if len(problem.rows) > self.limits.constraint_limit:
            raise UnsupportedProblem("expanded constraint limit exceeded")
        self.trace.append(
            Step(
                kind=StepKind.FORMULATION,
                at=_now(),
                message=f"Expanded {len(self.prepared.references)} scalar/Movement symbols and {len(problem.rows)} affine constraints; limits {self.limits.symbol_limit}/{self.limits.constraint_limit}.",
            )
        )
        if self.view.requirements.estimates:
            self.diagnose(
                "estimates_unused",
                "Simplex feasibility uses no initial primal estimate; estimates are not assignments.",
            )
        self.diagnose(
            "solver_scaling",
            json.dumps(
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
        self.checkpoint()
        return problem

    def solve(self, problem: compiler.Compiled) -> Result:
        """Retain backend evidence without treating its candidate as accepted."""
        assert self.limits is not None
        self.result = self.backend.solve(
            problem,
            limits=self.limits,
            remaining=self.limits.time_limit - (time.monotonic() - self.clock),
        )
        self.implementations.extend(self.result.implementations)
        self.diagnose(
            "solver_termination",
            json.dumps(
                {"termination": self.result.termination, **self.result.evidence},
                allow_nan=False,
            ),
        )
        self.trace.append(
            Step(
                kind=StepKind.SOLVE,
                at=_now(),
                message=f"Backend returned {self.result.termination}; independent acceptance follows when a candidate exists.",
            )
        )
        return self.result

    def accept(self, result: Result) -> None:
        """Check a serialized candidate against the original expressions."""
        assert self.prepared is not None
        limited = result.termination in {
            "worker_deadline",
            "maxTimeLimit",
            "iterationLimit",
            "objectiveLimit",
        }
        self.completion = (
            CompletionStatus.LIMITED if limited else CompletionStatus.COMPLETED
        )
        self.solution = SolutionStatus.UNKNOWN
        if result.termination == "provenInfeasible":
            self.solution = SolutionStatus.INFEASIBLE
        elif result.termination in {"error", "interrupted"}:
            self.completion = CompletionStatus.FAILED
        elif result.candidate is not None:
            candidate = publication.candidate(
                self.prepared, result.candidate, run_id=self.run_id
            )
            checked = acceptance.check(
                self.prepared, candidate, tolerances=self.tolerances
            )
            self.implementations.append(
                Implementation(
                    kind=ImplementationKind.EVALUATOR,
                    name="rangekeeper.scalar.original_expressions",
                    version=fingerprint("evaluator"),
                )
            )
            self.findings.extend(checked.diagnostics)
            if checked.accepted:
                self.output, self.solution = candidate, SolutionStatus.FEASIBLE
                self.diagnose(
                    "feasible_candidate",
                    "Original expressions, assignments and bounds accepted. No uniqueness or optimization claim is made.",
                )
                rank, count = result.evidence.get("equality_rank"), result.evidence.get(
                    "unknown_count"
                )
                if isinstance(rank, int) and isinstance(count, int) and rank < count:
                    self.diagnose(
                        (
                            "underdetermined"
                            if not result.evidence.get("has_bounds")
                            else "uniqueness_not_assessed"
                        ),
                        f"Numerical equality rank {rank} for {count} unknowns (NumPy SVD default threshold). Bounds may restrict freedom; this is one accepted candidate, not a uniqueness proof.",
                        severity=Severity.WARNING,
                    )
            else:
                self.completion = CompletionStatus.FAILED
                self.diagnose(
                    "numerical_rejection",
                    "Serialized candidate failed independent acceptance; no output was published.",
                    severity=Severity.ERROR,
                )

    def finish(self) -> Run:
        """Validate the final report, then persist output before its producing Run."""
        # No returned worker evidence means no claim that its iteration setting or
        # solver implementation actually ran. The parent deadline still applies.
        effective = (
            self.limits.record()
            if self.limits
            and self.result
            and self.result.termination != "worker_deadline"
            else (
                Settings(
                    time_limit=self.limits.time_limit,
                    symbol_limit=self.limits.symbol_limit,
                    constraint_limit=self.limits.constraint_limit,
                )
                if self.limits
                else Settings()
            )
        )
        if self.result is None or self.result.termination == "worker_deadline":
            self.diagnose(
                "settings_adjusted",
                "relative_tolerance and iteration_limit were not applied by a completed solver invocation; time_limit applies to the parent attempt budget when preparation established it. No infeasibility follows.",
                severity=Severity.WARNING,
            )
        if self.output is not None:
            self.trace.append(
                Step(
                    kind=StepKind.PUBLICATION,
                    at=_now(),
                    document=self.output.id,
                    message="Accepted serialized immutable Model; store output before finalized Run.",
                )
            )
        self.diagnose(
            "attempt_timing",
            f"Elapsed monotonic time before persistence: {time.monotonic() - self.clock:.9f} seconds.",
        )
        run = Run(
            RunRecord(
                metadata=Metadata(
                    id=self.run_id, schema_version=document_version("Run")
                ),
                specification=self.specification.id,
                outputs=() if self.output is None else (self.output.id,),
                report=Report(
                    status=Status(completion=self.completion, solution=self.solution),
                    runtime=Runtime(
                        started_at=self.started,
                        finished_at=_now(),
                        implementations=tuple(self.implementations),
                        settings=effective,
                    ),
                    diagnostics=tuple(self.findings),
                    trace=tuple(self.trace),
                    outcomes=() if self.prepared is None else self.prepared.outcomes,
                ),
            )
        )
        resolver = (
            self.store
            if self.output is None
            else publication.CandidateResolver(self.output, self.store)
        )
        validate_run(run, resolver=resolver, units=self.units).raise_if_invalid()
        if self.output is not None:
            self.store.put(self.output)
        self.store.put(run)
        return run
