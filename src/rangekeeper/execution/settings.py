"""Account for requested settings without conflating solver and acceptance criteria."""

import math
from dataclasses import dataclass

from rangekeeper.run import Severity
from rangekeeper.schema.records import Diagnostic, Settings
from rangekeeper.shared.codes import Code


@dataclass(frozen=True, kw_only=True)
class Limits:
    """The budget of one leaf attempt.

    ``time_limit`` is in seconds and covers preparation and the backend.
    ``iteration_limit`` counts simplex iterations. ``symbol_limit`` and
    ``constraint_limit`` bound the size of the affine problem.
    """

    time_limit: float = 30
    iteration_limit: int = 100000
    symbol_limit: int = 10000
    constraint_limit: int = 20000

    def __post_init__(self) -> None:
        time = self.time_limit
        if isinstance(time, bool) or not isinstance(time, (int, float)):
            raise TypeError("time_limit must be a number")
        if not math.isfinite(time) or time <= 0:
            raise ValueError("time_limit must be finite and positive")
        for name in ("iteration_limit", "symbol_limit", "constraint_limit"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")

    def record(self) -> Settings:
        """Return these limits as a Settings record."""
        return Settings(
            time_limit=self.time_limit,
            iteration_limit=self.iteration_limit,
            symbol_limit=self.symbol_limit,
            constraint_limit=self.constraint_limit,
        )


def resolve(
    requested: Settings | None,
    *,
    defaults: Limits,
) -> tuple[Limits, tuple[Diagnostic, ...]]:
    """Return applied limits and explicit diagnostics for unapplied/adjusted requests.

    A requested setting replaces its default from ``defaults``. A backend may
    adjust a limit further; it reports that itself. The generic
    relative_tolerance has no justified mapping to the absolute feasibility
    tolerances of the solver. Report it as unapplied, never as effective.
    Independent dimensional acceptance has its own policy.
    """
    findings = []
    time = (
        float(requested.time_limit)
        if requested and requested.time_limit is not None
        else defaults.time_limit
    )
    iterations = (
        requested.iteration_limit
        if requested and requested.iteration_limit is not None
        else defaults.iteration_limit
    )
    if requested and requested.relative_tolerance is not None:
        findings.append(
            Diagnostic(
                severity=Severity.WARNING,
                code=Code.SETTINGS_ADJUSTED.value,
                message=(
                    f"relative_tolerance={requested.relative_tolerance} is not applied: this scalar LP adapter "
                    "uses explicit absolute primal/dual solver tolerances, not a relative convergence criterion. "
                    "Independent dimensional acceptance is recorded separately."
                ),
                values={
                    "settings": ["relative_tolerance"],
                    "disposition": "not_applied",
                },
            )
        )
    return Limits(
        time_limit=time,
        iteration_limit=iterations,
        symbol_limit=(
            requested.symbol_limit
            if requested and requested.symbol_limit is not None
            else defaults.symbol_limit
        ),
        constraint_limit=(
            requested.constraint_limit
            if requested and requested.constraint_limit is not None
            else defaults.constraint_limit
        ),
    ), tuple(findings)
