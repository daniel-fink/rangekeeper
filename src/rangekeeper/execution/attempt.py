"""One leaf attempt: run the pure stages in order and collect their evidence."""

import time
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID, uuid4

from rangekeeper import money
from rangekeeper.execution import (
    acceptance,
    assembly,
    compiler,
    dates,
    expansion,
    preparation,
    publication,
    settings,
    staging,
    statuses,
)
from rangekeeper.execution.analysis import Analysis
from rangekeeper.execution.backends import Backend, registry
from rangekeeper.execution.backends.base import BackendResult
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.errors import (
    AttemptDeadlineError,
)
from rangekeeper.execution.implementation import fingerprint
from rangekeeper.execution.outcome import Outcome
from rangekeeper.execution.rule.provisional import broken_dates
from rangekeeper.execution.rule.sequence import (
    Decisions,
    Progress,
    Solver,
    check_past,
    run_rules,
)
from rangekeeper.market.paths import Paths
from rangekeeper.model import Model
from rangekeeper.quantity import Quantity, UnitSystem, unit_systems
from rangekeeper.run import ImplementationKind, StepKind
from rangekeeper.run._rule.availability import path_amounts, path_known
from rangekeeper.run._rule.stored import stored_evidence
from rangekeeper.run._rule.trace import TraceFacts, candidate_values, check_trace
from rangekeeper.schema.records import (
    CompletionStatus,
    Diagnostic,
    Implementation,
    Reference,
    Report,
    RuleEvidence,
    RunStatus,
    Runtime,
    Settings,
    Severity,
    SolutionStatus,
    Step,
)
from rangekeeper.schema.runtime import UNSET, JSONValue, Unset
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    ContractError,
    DecisionError,
    RangekeeperError,
    ValidationError,
)
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.specification import Composition, Specification
from rangekeeper.specification._paths import load as load_paths
from rangekeeper.specification.rule._query import RuleQuery


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Attempt:
    """One leaf attempt owns its deadline, diagnostics and trace.

    It calls the pure stages in order: validate, bind roles, build the problem,
    solve, make a candidate, verify and assemble. It maps each expected failure
    to a status, so a failure still gives a finalized Run. It stores nothing.

    ``rules`` are the rules of the case and ``parameters`` the values that they
    read. With rules, the rules stage follows ``bind_roles`` (ADR-021) and
    ``decisions`` holds its result; the trace check runs on the candidate, and the
    report records the trace.
    """

    def __init__(
        self,
        specification: Specification,
        view: Composition | ValidationError,
        *,
        config: ExecutionConfig,
        backend: Backend,
        resolver: DocumentResolver,
        rules: Sequence[RuleQuery] = (),
        parameters: Mapping[str, Quantity] | None = None,
    ) -> None:
        self.config, self.backend = config, backend
        self.rules, self.parameters = tuple(rules), dict(parameters or {})
        self.decisions: Decisions | None = None
        self.progress: Progress | None = None
        self.verified = False
        self.units: UnitSystem | None = config.units
        self.specification, self.view = specification, view
        self.resolver = resolver
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
        conclusion = statuses.failure(error, self.reached)
        self.completion, self.solution = conclusion.completion, conclusion.solution
        code = conclusion.code
        if code is None:
            # A row without a code is for an error that carries its own.
            assert isinstance(error, RangekeeperError)
            code = error.code
        # The diagnostic locates the error; a ValidationError's issues keep
        # their own documents and targets in values.
        located = error if isinstance(error, RangekeeperError) else None
        if isinstance(error, ValidationError):
            located = None
        targets = () if located is None else located.targets
        # The error's structured fields, so that a reader needs no message text.
        values = statuses.diagnosed(error)
        references = statuses.referenced(error)
        self.diagnose(
            code,
            str(error),
            severity=conclusion.severity,
            document=UNSET if located is None else located.document_id or UNSET,
            target=targets[0] if len(targets) == 1 else UNSET,
            references=references or UNSET,
            values=values or UNSET,
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
            composition=self.view, resolver=self.resolver, units=self.units
        )
        self.checkpoint()
        self.binding = preparation.bind_roles(
            validation=self.validation, checkpoint=self.checkpoint
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
        # The date equations determine dates first (#280); then each Flow
        # equation and equation function is written period by period (#276).
        # The candidate and verification keep every original assertion.
        bound = self.decide(self.binding)
        settled = dates.settle(bound)
        self.name_broken_dates(bound, settled)
        self.binding, expanded = expansion.expand_settled(
            settled, original=bound.assertions
        )
        staged = staging.stage(
            expanded,
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
                    f" {staged.stage_count} earlier stages determined {len(staged.determined)} values."
                    if staged.determined
                    else ""
                )
                + (
                    f" Picked the active sides of {len(staged.sides)} max and min calls in {staged.rounds} rounds."
                    if staged.sides
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

    def decide(self, binding: preparation.Binding) -> preparation.Binding:
        """Run the rules stage, and return ``binding`` with the decided values fixed."""
        if not self.rules:
            return binding
        assert self.limits is not None
        self.progress = Progress()
        try:
            self.decisions = run_rules(
                binding=binding,
                rules=self.rules,
                parameters=self.parameters,
                paths=self.paths(binding),
                progress=self.progress,
                solver=Solver(
                    backend=self.backend,
                    config=self.config,
                    limits=self.limits,
                    checkpoint=self.checkpoint,
                ),
            )
        except ContractError as error:
            # Validation found the static problems, so this one is of this case.
            raise DecisionError(
                str(error),
                code=error.code,
                document_id=binding.model.id,
                targets=error.targets,
                values=error.values,
            ) from error
        self.trace.append(
            Step(
                kind=StepKind.SOLVE,
                at=_now(),
                message=f"Rules decided {len(self.decisions.decided)} values with "
                f"{self.decisions.solves} provisional solves.",
            )
        )
        return self.decisions.bind(binding)

    def name_broken_dates(
        self, bound: preparation.Binding, settled: preparation.Binding
    ) -> None:
        """Name each date constraint that the decisions break (ADR-021, cell 7)."""
        if self.decisions is None:
            return
        for text in broken_dates(bound, settled=settled):
            self.diagnose(
                Code.CONSTRAINT_RESIDUAL,
                f"The decided dates break the constraint {text}.",
                severity=Severity.ERROR,
                values={"equation": text},
            )

    def paths(self, binding: preparation.Binding) -> Paths | None:
        """Return the Paths document of the case's path, when it has one."""
        path = binding.composition.requirements.path
        return None if path is None else load_paths(self.resolver, path.paths)

    def check_decisions(self, candidate: Model) -> None:
        """Check the candidate against the decisions and their trace (ADR-021)."""
        if self.decisions is None:
            return
        assert self.binding is not None
        tolerances = self.config.tolerances
        check_past(
            binding=self.binding,
            decisions=self.decisions,
            solved=candidate_values(candidate),
            tolerances=tolerances,
        )
        path = self.binding.composition.requirements.path
        paths = self.paths(self.binding)
        known: Mapping[UUID, date] = {}
        amounts: Mapping[UUID, Quantity] = {}
        if path is not None and paths is not None:
            known = path_known(path=path, paths=paths)
            amounts = path_amounts(path=path, paths=paths)
        check_trace(
            rules=self.rules,
            checks=self.decisions.checks,
            facts=TraceFacts(
                candidate=candidate,
                path_known=known,
                path_amounts=amounts,
                parameters=self.parameters,
                units=self.binding.units,
                absolute=tolerances.absolute,
                relative=tolerances.relative,
            ),
        )
        self.verified = True

    def rule_evidence(self) -> RuleEvidence | Unset:
        """Return the stored trace, when the rules stage recorded any of it."""
        if self.progress is None or not self.progress.checks:
            return UNSET
        return stored_evidence(
            checks=self.progress.checks,
            provisional_solves=self.progress.solves,
            verified=self.verified,
        )

    def solve_stage(self, problem: compiler.AffineProblem) -> BackendResult:
        """Solve the affine rows of an earlier stage; the result is not a candidate."""
        assert self.limits is not None
        result = self.backend.solve(
            problem=problem,
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
                problem=problem,
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
                binding=self.binding,
                unknowns={**result.candidate, **staged.determined},
                run_id=self.run_id,
            )
            checked = acceptance.verify(
                binding=self.binding,
                candidate=candidate,
                tolerances=self.config.tolerances,
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
            if checked.passed:
                self.check_decisions(candidate)
                if not problem.analysis.underdetermined:
                    acceptance.check_fixed_irrs(
                        binding=self.binding, candidate=candidate
                    )
                self.diagnose(
                    Code.FEASIBLE_CANDIDATE,
                    "Original expressions, assignments and bounds accepted. No uniqueness or optimization claim is made.",
                )
                self.conclude(candidate, problem.analysis)
            else:
                self.completion = CompletionStatus.FAILED
                self.diagnose(
                    Code.NUMERICAL_REJECTION,
                    "Serialized candidate failed independent acceptance; no output was published.",
                    severity=Severity.ERROR,
                )

    def conclude(self, candidate: Model, analysis: Analysis) -> None:
        """Set the solution of a verified candidate, and publish it when it may.

        A candidate whose equations determine every unknown is feasible and is
        the output. Otherwise the solution is underdetermined, a diagnostic
        names the free unknowns, and the candidate is the output only with
        ``ExecutionConfig.allow_underdetermined`` (ADR-016).
        """
        if not analysis.underdetermined:
            self.output, self.solution = candidate, SolutionStatus.FEASIBLE
            return
        self.solution = SolutionStatus.UNDERDETERMINED
        if self.config.allow_underdetermined:
            self.output = candidate
        self.diagnose_freedom(analysis)

    def diagnose_freedom(self, analysis: Analysis) -> None:
        """Name the unknowns that the equality rows of an accepted solve leave free.

        The code is ``uniqueness_not_assessed`` when a bound reads one of
        them, and ``underdetermined`` otherwise. Either way the Outcome is
        ``UNDERDETERMINED``: the equations do not determine these values.
        ``values.unknowns`` gives their keys, so that a reader needs no output.
        """
        assert self.binding is not None
        free = [self.binding.references[id] for id in analysis.undetermined]
        keys = [self.binding.key(ref) for ref in free]
        bounded = (
            " Bounds read some of them and may restrict them; no uniqueness check ran."
            if analysis.bounded
            else ""
        )
        published = (
            " The candidate holds one value for each; it is published on request."
            if self.output is not None
            else " No output is published."
        )
        self.diagnose(
            Code.UNIQUENESS_NOT_ASSESSED if analysis.bounded else Code.UNDERDETERMINED,
            f"Numerical equality rank {analysis.equality_rank} for {analysis.unknown_count} unknowns."
            " The equations do not determine these free unknowns: "
            + ", ".join(keys)
            + "."
            + bounded
            + published,
            severity=Severity.WARNING,
            document=self.binding.model.id,
            references=tuple(free),
            values={
                "equality_rank": analysis.equality_rank,
                "unknown_count": analysis.unknown_count,
                "unknowns": list(keys),
            },
        )

    def finish(self) -> Outcome:
        """Assemble the Outcome. The caller validates its Run, once for the tree."""
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
            status=RunStatus(completion=self.completion, solution=self.solution),
            runtime=Runtime(
                started_at=self.started,
                finished_at=_now(),
                implementations=tuple(self.implementations),
                settings=effective,
            ),
            diagnostics=tuple(self.findings),
            trace=tuple(self.trace),
            rule_evidence=self.rule_evidence(),
            decision_evidence=(
                () if self.binding is None else self.binding.decision_evidence
            ),
        )
        return assembly.assemble(
            specification=self.specification,
            report=report,
            id=self.run_id,
            output=self.output,
        )
