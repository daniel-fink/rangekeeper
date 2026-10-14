"""Account for requested settings without conflating solver and acceptance criteria."""

from rangekeeper.run import Severity

from dataclasses import dataclass

from rangekeeper.schema.records import Settings, Diagnostic


@dataclass(frozen=True)
class Limits:
    """Effective leaf-attempt budget and deterministic simplex iteration limit."""

    time_limit: float = 30
    iteration_limit: int = 100000
    symbol_limit: int = 10000
    constraint_limit: int = 20000

    def record(self) -> Settings:
        return Settings(
            time_limit=self.time_limit,
            iteration_limit=self.iteration_limit,
            symbol_limit=self.symbol_limit,
            constraint_limit=self.constraint_limit,
        )


def resolve(requested: Settings | None) -> tuple[Limits, tuple[Diagnostic, ...]]:
    """Return applied limits and explicit diagnostics for unapplied/adjusted requests.

    The generic relative_tolerance has no justified mapping to HiGHS absolute
    primal/dual feasibility tolerances. Report it as unapplied, never as effective.
    Independent dimensional acceptance has its own policy. Presolve is enabled;
    iteration_limit counts simplex iterations, not presolve reductions.
    """
    findings = []
    time = (
        float(requested.time_limit)
        if requested and requested.time_limit is not None
        else 30.0
    )
    iterations = (
        requested.iteration_limit
        if requested and requested.iteration_limit is not None
        else 100000
    )
    if iterations > 2147483647:
        iterations = 2147483647
        findings.append(
            Diagnostic(
                severity=Severity.WARNING,
                code="settings_adjusted",
                message="iteration_limit clamped to HiGHS maximum 2147483647.",
            )
        )
    if requested and requested.relative_tolerance is not None:
        findings.append(
            Diagnostic(
                severity=Severity.WARNING,
                code="settings_adjusted",
                message=(
                    f"relative_tolerance={requested.relative_tolerance} is not applied: this scalar LP adapter "
                    "uses explicit absolute primal/dual solver tolerances, not a relative convergence criterion. "
                    "Independent dimensional acceptance is recorded separately."
                ),
            )
        )
    return Limits(
        time,
        iterations,
        (
            requested.symbol_limit
            if requested and requested.symbol_limit is not None
            else 10000
        ),
        (
            requested.constraint_limit
            if requested and requested.constraint_limit is not None
            else 20000
        ),
    ), tuple(findings)
