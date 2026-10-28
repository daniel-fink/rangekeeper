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
)
from rangekeeper.execution.backends import Backend, registry
from rangekeeper.execution.backends.base import Result
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.errors import (
    AttemptDeadlineError,
    BackendUnavailableError,
    NumericalError,
    UnsupportedError,
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
from rangekeeper.shared.errors import UnitError, ValidationError
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
        self.binding: preparation.Binding | None = None
        self.result: Result | None = None
        self.output: Model | None = None
        self.completion: CompletionStatus = CompletionStatus.FAILED
        self.solution: SolutionStatus = SolutionStatus.NOT_ASSESSED

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
            problem = self.prepare()
            result = self.solve(problem)
            self.accept(result)
        except AttemptDeadlineError as error:
            self.completion, self.solution = (
                CompletionStatus.LIMITED,
                SolutionStatus.NOT_ASSESSED,
            )
            self.diagnose(Code.ATTEMPT_DEADLINE, str(error), severity=Severity.WARNING)
        except ValidationError as error:
            self.completion, self.solution = (
                CompletionStatus.FAILED,
                (
                    SolutionStatus.NOT_ASSESSED
                    if self.binding is None
                    else SolutionStatus.UNKNOWN
                ),
            )
            self.diagnose(
                (
                    Code.SPECIFICATION_INVALID
                    if self.binding is None
                    else Code.NUMERICAL_REJECTION
                ),
                str(error),
                severity=Severity.ERROR,
            )
        except (UnsupportedError, UnitError) as error:
            self.completion, self.solution = (
                CompletionStatus.FAILED,
                (
                    SolutionStatus.NOT_ASSESSED
                    if self.result is None
                    else SolutionStatus.UNKNOWN
                ),
            )
            self.diagnose(
                (
                    error.code
                    if isinstance(error, UnsupportedError)
                    else Code.UNSUPPORTED_CAPABILITY
                ),
                str(error),
                severity=Severity.ERROR,
                document=(
                    error.document
                    if isinstance(error, UnsupportedError) and error.document
                    else UNSET
                ),
                target=(
                    error.target
                    if isinstance(error, UnsupportedError) and error.target
                    else UNSET
                ),
            )
        except BackendUnavailableError as error:
            self.diagnose(Code.BACKEND_UNAVAILABLE, str(error), severity=Severity.ERROR)
        except (NumericalError, ArithmeticError) as error:
            self.completion, self.solution = (
                CompletionStatus.FAILED,
                SolutionStatus.UNKNOWN,
            )
            self.diagnose(Code.NUMERICAL_FAILURE, str(error), severity=Severity.ERROR)

        return self.finish()

    def prepare(self) -> compiler.AffineProblem:
        """Validate, bind roles and build the problem within one deadline."""
        if isinstance(self.view, ValidationError):
            raise self.view
        self.limits, adjustments = settings.resolve(
            self.view.requirements.settings, defaults=self.config.limits
        )
        self.findings.extend(adjustments)
        validation = preparation.validate(
            self.view, resolver=self.resolver, units=self.units
        )
        self.checkpoint()
        self.binding = preparation.bind_roles(validation, checkpoint=self.checkpoint)
        self.checkpoint()
        self.trace.append(
            Step(
                kind=StepKind.VALIDATION,
                at=_now(),
                document=self.specification.id,
                message="Validated additive composition, exact Model pin, scalar roles and recorded units.",
            )
        )
        problem = compiler.build_problem(
            self.binding, limits=self.limits, checkpoint=self.checkpoint
        )
        self.trace.append(
            Step(
                kind=StepKind.FORMULATION,
                at=_now(),
                message=f"Expanded {len(self.binding.references)} scalar/Movement symbols and {len(problem.rows)} affine constraints; limits {self.limits.symbol_limit}/{self.limits.constraint_limit}.",
            )
        )
        if self.view.requirements.estimates:
            self.diagnose(
                Code.ESTIMATES_UNUSED,
                "Simplex feasibility uses no initial primal estimate; estimates are not assignments.",
            )
        self.diagnose(
            Code.SOLVER_SCALING,
            f"Scaled {len(problem.rows)} affine constraints; values.rows gives each divisor and residual unit.",
            values={
                "rows": [
                    {
                        "constraint": str(row.assertion.constraint.id),
                        "divisor": row.scale,
                        "residual_units": row.residual.units,
                    }
                    for row in problem.rows
                ]
            },
        )
        self.checkpoint()
        return problem

    def solve(self, problem: compiler.AffineProblem) -> Result:
        """Retain backend evidence without treating its candidate as accepted."""
        assert self.limits is not None
        self.result = self.backend.solve(
            problem,
            limits=self.limits,
            remaining=self.limits.time_limit - (time.monotonic() - self.clock),
            options=self.config.backend_options,
        )
        self.implementations.extend(self.result.implementations)
        self.diagnose(
            Code.SOLVER_TERMINATION,
            f"Backend returned {self.result.termination}; values gives the solver evidence.",
            # Backends return finite JSON evidence; the record checks it again.
            values={
                "termination": self.result.termination,
                **cast(Mapping[str, JSONValue], self.result.evidence),
            },
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
        assert self.binding is not None
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
            candidate = publication.make_candidate(
                self.binding, result.candidate, run_id=self.run_id
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
                rank, count = (
                    result.evidence.get("equality_rank"),
                    result.evidence.get("unknown_count"),
                )
                if isinstance(rank, int) and isinstance(count, int) and rank < count:
                    # Unknowns that no row constrains were set to zero; name them.
                    unconstrained = result.evidence.get(
                        "unconstrained_values_initialized_to_zero"
                    )
                    free = [
                        self.binding.references[UUID(id)]
                        for id in (
                            unconstrained if isinstance(unconstrained, list) else ()
                        )
                    ]
                    self.diagnose(
                        (
                            Code.UNDERDETERMINED
                            if not result.evidence.get("has_bounds")
                            else Code.UNIQUENESS_NOT_ASSESSED
                        ),
                        f"Numerical equality rank {rank} for {count} unknowns (NumPy SVD default threshold). Bounds may restrict freedom; this is one accepted candidate, not a uniqueness proof."
                        + (
                            " Unconstrained unknowns initialized to zero: "
                            + ", ".join(str(ref.target) for ref in free)
                            + "."
                            if free
                            else ""
                        ),
                        severity=Severity.WARNING,
                        document=self.binding.model.id if free else UNSET,
                        references=tuple(free) if free else UNSET,
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
