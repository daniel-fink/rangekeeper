"""One leaf attempt: run the pure stages in order and collect their evidence."""

import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from rangekeeper import money
from rangekeeper.execution import (
    acceptance,
    assembly,
    compiler,
    preparation,
    publication,
    settings,
    staging,
    statuses,
)
from rangekeeper.execution.backends import Backend, registry
from rangekeeper.execution.backends.base import BackendResult
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.errors import (
    AttemptDeadlineError,
)
from rangekeeper.execution.implementation import fingerprint
from rangekeeper.execution.outcome import Outcome
from rangekeeper.model import Model
from rangekeeper.quantity import UnitSystem, unit_systems
from rangekeeper.run import ImplementationKind, StepKind
from rangekeeper.schema.records import (
    CompletionStatus,
    Diagnostic,
    Implementation,
    Reference,
    Report,
    Runtime,
    Settings,
    Severity,
    SolutionStatus,
    Status,
    Step,
)
from rangekeeper.schema.runtime import UNSET, JSONValue, Unset
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import RangekeeperError, ValidationError
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.specification import Composition, Specification


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Attempt:
    """One leaf attempt owns its deadline, diagnostics and trace.

    It calls the pure stages in order: validate, bind roles, build the problem,
    solve, make a candidate, verify and assemble. It maps each expected failure
    to a status, so a failure still gives a finalized Run. It stores nothing.
    """

    def __init__(
        self,
        config: ExecutionConfig,
        backend: Backend,
        specification: Specification,
        view: Composition | ValidationError,
        *,
        resolver: DocumentResolver,
        validate: bool = True,
    ) -> None:
        self.config, self.backend = config, backend
        self.units: UnitSystem | None = config.units
        self.specification, self.view = specification, view
        self.resolver, self.validate = resolver, validate
        self.run_id, self.started, self.clock = uuid4(), _now(), time.monotonic()
        self.findings: list[Diagnostic] = []
        self.trace: list[Step] = []
        solver = registry.describe(backend)
        self.implementations = [
            Implementation(
                kind=ImplementationKind.COMPILER,
                name="rangekeeper.scalar",
                version=fingerprint("compiler"),
            ),
            Implementation(
                kind=ImplementationKind.SOLVER,
                name=solver.qualified_name,
                version=solver.fingerprint,
            ),
            # The numerical convention for currency amounts (ADR-023).
            Implementation(
                kind=ImplementationKind.CONVENTION,
                name="rangekeeper.money",
                version=money.CONVENTION,
            ),
        ]
        self.limits: settings.Limits | None = None
        self.validation: preparation.Validation | None = None
        self.binding: preparation.Binding | None = None
        self.result: BackendResult | None = None
        self.output: Model | None = None
        self.completion: CompletionStatus = CompletionStatus.FAILED
        self.solution: SolutionStatus = SolutionStatus.NOT_ASSESSED
        self.reached = statuses.Reached.NOTHING

    def diagnose(
        self,
        code: Code,
        message: str,
        *,
        severity: Severity = Severity.INFO,
        document: UUID | Unset = UNSET,
        target: UUID | Unset = UNSET,
        references: tuple[Reference, ...] | Unset = UNSET,
        values: Mapping[str, JSONValue] | Unset = UNSET,
    ) -> None:
        """Attach an outcome or adjustment to this attempt's report."""
        self.findings.append(
            Diagnostic(
                severity=severity,
                code=Code(code).value,
                message=message,
                document=document,
                target=target,
                references=references,
                values=values,
            )
        )

    def checkpoint(self) -> None:
        """Raise AttemptDeadlineError when this attempt's time limit has elapsed."""
        if (
            self.limits is not None
            and time.monotonic() - self.clock >= self.limits.time_limit
        ):
            raise AttemptDeadlineError(
                "execution deadline reached during preparation or compilation"
            )

    def execute(self) -> Outcome:
        """Run the stages, account for each expected failure, and return the Outcome."""
        try:
            staged = self.prepare()
            if staged.ended is None:
                result = self.solve(staged.problem)
            else:
                result = self.record(staged.ended)
            self.accept(staged, result)
        except statuses.EXPECTED as error:
            self.fail(error)
        return self.finish()

    def fail(self, error: BaseException) -> None:
        """Set the status and diagnostic of an expected failure from its table."""
        status = statuses.failure(error, self.reached)
        self.completion, self.solution = status.completion, status.solution
        code = status.code
        if code is None:
            # A row without a code is for an error that carries its own.
            assert isinstance(error, RangekeeperError)
            code = error.code
        self.diagnose(
            code,
            str(error),
            severity=status.severity,
            document=getattr(error, "document", None) or UNSET,
            target=getattr(error, "target", None) or UNSET,
        )

    def prepare(self) -> staging.Staged:
        """Validate, bind roles and build the staged problem within one deadline."""
        if isinstance(self.view, ValidationError):
            raise self.view
        self.limits, adjustments = settings.resolve(
            self.view.requirements.settings, defaults=self.config.limits
        )
        self.findings.extend(adjustments)
        self.validation = preparation.validate(
            self.view, resolver=self.resolver, units=self.units
        )
        self.checkpoint()
        self.binding = preparation.bind_roles(
            self.validation, checkpoint=self.checkpoint
        )
        self.reached = statuses.Reached.BOUND
        self.checkpoint()
        self.trace.append(
            Step(
                kind=StepKind.VALIDATION,
                at=_now(),
                document=self.specification.id,
                message="Validated additive composition, exact Model pin, scalar roles and recorded units.",
            )
        )
        staged = staging.stage(
            self.binding,
            solve=self.solve_stage,
            limits=self.limits,
            checkpoint=self.checkpoint,
        )
        problem = staged.problem
        self.trace.append(
            Step(
                kind=StepKind.FORMULATION,
                at=_now(),
                message=f"Expanded {len(self.binding.references)} scalar/Movement symbols and {len(problem.rows)} affine constraints; limits {self.limits.symbol_limit}/{self.limits.constraint_limit}."
                + (
                    f" {len(staged.stages)} earlier stages determined {len(staged.determined)} values."
                    if staged.stages
                    else ""
                ),
            )
        )
        if self.view.requirements.estimates:
            self.diagnose(
                Code.ESTIMATES_UNUSED,
                "Simplex feasibility uses no initial primal estimate; estimates are not assignments.",
            )
        self.checkpoint()
        return staged

    def solve_stage(self, problem: compiler.AffineProblem) -> BackendResult:
        """Solve the affine rows of an earlier stage; the result is not a candidate."""
        assert self.limits is not None
        result = self.backend.solve(
            problem,
            limits=self.limits,
            remaining=self.limits.time_limit - (time.monotonic() - self.clock),
            options=self.config.backend_options,
        )
        self.trace.append(
            Step(
                kind=StepKind.SOLVE,
                at=_now(),
                message=f"Stage of {len(problem.rows)} affine constraints: backend returned {result.termination.value}.",
            )
        )
        self.checkpoint()
        return result

    def solve(self, problem: compiler.AffineProblem) -> BackendResult:
        """Retain backend evidence without treating its candidate as accepted."""
        assert self.limits is not None
        return self.record(
            self.backend.solve(
                problem,
                limits=self.limits,
                remaining=self.limits.time_limit - (time.monotonic() - self.clock),
                options=self.config.backend_options,
            )
        )

    def record(self, result: BackendResult) -> BackendResult:
        """Record the backend result that ends the solve, and its evidence."""
        self.result = result
        self.reached = statuses.Reached.SOLVED
        self.implementations.extend(self.result.implementations)
        self.findings.extend(self.result.diagnostics)
        self.diagnose(
            Code.SOLVER_TERMINATION,
            f"Backend returned {self.result.termination.value}; values gives the solver evidence.",
            # Backends return finite JSON evidence; the record checks it again.
            values={
                "termination": self.result.termination.value,
                **cast(Mapping[str, JSONValue], self.result.evidence),
            },
        )
        self.trace.append(
            Step(
                kind=StepKind.SOLVE,
                at=_now(),
                message=f"Backend returned {self.result.termination.value}; independent acceptance follows when a candidate exists.",
            )
        )
        return self.result

    def accept(self, staged: staging.Staged, result: BackendResult) -> None:
        """Check a serialized candidate against the original expressions.

        The candidate holds the backend's values and the values that earlier
        stages determined.
        """
        assert self.binding is not None
        problem = staged.problem
        ending = statuses.TERMINATIONS[result.termination]
        self.completion, self.solution = ending.completion, ending.solution
        if ending.verify and result.candidate is not None and staged.ended is None:
            candidate = publication.make_candidate(
                self.binding,
                {**result.candidate, **staged.determined},
                run_id=self.run_id,
            )
            checked = acceptance.verify(
                self.binding, candidate, tolerances=self.config.tolerances
            )
            units = unit_systems.describe(self.binding.units)
            self.implementations.extend(
                (
                    Implementation(
                        kind=ImplementationKind.EVALUATOR,
                        name="rangekeeper.scalar.original_expressions",
                        version=fingerprint("evaluator"),
                    ),
                    Implementation(
                        kind=ImplementationKind.EVALUATOR,
                        name=units.qualified_name,
                        version=units.fingerprint,
                    ),
                )
            )
            self.findings.extend(checked.diagnostics)
            if checked.accepted:
                self.output, self.solution = candidate, SolutionStatus.FEASIBLE
                self.diagnose(
                    Code.FEASIBLE_CANDIDATE,
                    "Original expressions, assignments and bounds accepted. No uniqueness or optimization claim is made.",
                )
                analysis = problem.analysis
                if analysis.underdetermined:
                    free = [self.binding.references[id] for id in analysis.undetermined]
                    self.diagnose(
                        (
                            Code.UNIQUENESS_NOT_ASSESSED
                            if analysis.has_bounds
                            else Code.UNDERDETERMINED
                        ),
                        f"Numerical equality rank {analysis.rank} for {analysis.unknown_count} unknowns. Bounds may restrict freedom; this is one accepted candidate, not a uniqueness proof."
                        + (
                            " The equations do not determine these free unknowns; the candidate holds one value for each: "
                            + ", ".join(str(ref.target) for ref in free)
                            + "."
                            if free
                            else ""
                        ),
                        severity=Severity.WARNING,
                        document=self.binding.model.id if free else UNSET,
                        references=tuple(free) if free else UNSET,
                        values={
                            "equality_rank": analysis.rank,
                            "unknown_count": analysis.unknown_count,
                        },
                    )
            else:
                self.completion = CompletionStatus.FAILED
                self.diagnose(
                    Code.NUMERICAL_REJECTION,
                    "Serialized candidate failed independent acceptance; no output was published.",
                    severity=Severity.ERROR,
                )

    def finish(self) -> Outcome:
        """Assemble the Outcome; validate its Run unless a later commit point will."""
        # No returned worker evidence means no claim that its iteration setting or
        # solver implementation actually ran. The parent deadline still applies.
        effective = (
            self.result.limits.record()
            if self.result is not None and self.result.limits is not None
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
        if self.result is None or self.result.limits is None:
            self.diagnose(
                Code.SETTINGS_ADJUSTED,
                "relative_tolerance and iteration_limit were not applied by a completed solver invocation; time_limit applies to the parent attempt budget when preparation established it. No infeasibility follows.",
                severity=Severity.WARNING,
                values={
                    "settings": ["relative_tolerance", "iteration_limit"],
                    "disposition": "not_applied",
                },
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
            Code.ATTEMPT_TIMING,
            f"Elapsed monotonic time before persistence: {time.monotonic() - self.clock:.9f} seconds.",
        )
        report = Report(
            status=Status(completion=self.completion, solution=self.solution),
            runtime=Runtime(
                started_at=self.started,
                finished_at=_now(),
                implementations=tuple(self.implementations),
                settings=effective,
            ),
            diagnostics=tuple(self.findings),
            trace=tuple(self.trace),
            rule_evidence=() if self.binding is None else self.binding.rule_evidence,
        )
        return assembly.assemble(
            self.specification,
            report,
            id=self.run_id,
            output=self.output,
            resolver=self.resolver,
            units=self.units if self.binding is None else self.binding.units,
            validate=self.validate,
        )
