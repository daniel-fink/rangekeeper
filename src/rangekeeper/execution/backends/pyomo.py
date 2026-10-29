"""Process-isolated Pyomo/HiGHS adapter with an enforced parent-side deadline."""

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

from rangekeeper.execution.backends.base import BackendResult, Termination
from rangekeeper.execution.compiler import AffineProblem, Row
from rangekeeper.execution.errors import (
    BackendUnavailableError,
    NumericalError,
    UnsupportedError,
)
from rangekeeper.execution.settings import Limits
from rangekeeper.schema.enums import Severity
from rangekeeper.schema.records import Diagnostic, Implementation
from rangekeeper.shared.codes import Code

# HiGHS reads its iteration limit as a 32-bit integer.
ITERATION_MAXIMUM = 2147483647
# A row coefficient at or below this, after scaling, is too small for HiGHS.
SMALLEST_COEFFICIENT = 1e-12
# A scaled constant at or above this is an infinite bound to HiGHS.
LARGEST_CONSTANT = 1e19
TERMINATIONS = {
    "convergenceCriteriaSatisfied": Termination.FEASIBLE,
    "provenInfeasible": Termination.INFEASIBLE,
    "maxTimeLimit": Termination.LIMITED,
    "iterationLimit": Termination.LIMITED,
    "objectiveLimit": Termination.LIMITED,
    "error": Termination.FAILED,
    "interrupted": Termination.FAILED,
}


class PyomoHighs:
    """Lower in a child process so a stalled native solver can be terminated.

    Only numerical rows cross the private JSON protocol; no solver object or
    mutable Model crosses it. Pyomo/highspy imports happen in the child. Timeout
    kills and reaps that process, discards partial output, and proves no infeasibility.

    ``options`` are HiGHS options. They replace the defaults of the worker, except
    for the options in ``RESERVED``, which the backend sets itself.

    The HiGHS limits live here. Each row is divided by ``max(1, largest absolute
    coefficient)``; a row whose scaled coefficients reach ``SMALLEST_COEFFICIENT``
    or whose scaled constant reaches ``LARGEST_CONSTANT`` raises UnsupportedError
    for its Constraint. An iteration limit above ``ITERATION_MAXIMUM`` is clamped.
    Pyomo termination conditions map to ``Termination`` through ``TERMINATIONS``;
    any other condition is ``UNKNOWN``. The raw condition is in the evidence as
    ``termination_condition``.
    """

    RESERVED = frozenset(
        {
            "log_file",
            "log_to_console",
            "output_flag",
            "simplex_iteration_limit",
            "threads",
            "time_limit",
        }
    )

    def solve(
        self,
        problem: AffineProblem,
        *,
        limits: Limits,
        remaining: float,
        options: Mapping[str, object] = MappingProxyType({}),
    ) -> BackendResult:
        """Solve a problem in a child process and return its BackendResult."""
        refused = sorted(self.RESERVED.intersection(options))
        if refused:
            raise UnsupportedError(
                "the pyomo-highs backend sets these HiGHS options itself: "
                + ", ".join(refused)
            )
        scales = tuple(self._scale(row) for row in problem.rows)
        findings = [
            Diagnostic(
                severity=Severity.INFO,
                code=Code.SOLVER_SCALING.value,
                message=f"Scaled {len(problem.rows)} affine constraints; values.rows gives each divisor and residual unit.",
                values={
                    "rows": [
                        {
                            "constraint": str(row.assertion.constraint.id),
                            "divisor": scale,
                            "residual_units": row.residual.units,
                        }
                        for row, scale in zip(problem.rows, scales, strict=True)
                    ]
                },
            )
        ]
        applied = limits
        if limits.iteration_limit > ITERATION_MAXIMUM:
            applied = replace(limits, iteration_limit=ITERATION_MAXIMUM)
            findings.append(
                Diagnostic(
                    severity=Severity.WARNING,
                    code=Code.SETTINGS_ADJUSTED.value,
                    message=f"iteration_limit clamped to HiGHS maximum {ITERATION_MAXIMUM}.",
                    values={
                        "settings": ["iteration_limit"],
                        "disposition": "clamped",
                        "effective": ITERATION_MAXIMUM,
                    },
                )
            )
        if remaining <= 0:
            return BackendResult(
                Termination.LIMITED,
                evidence={"termination_condition": "worker_deadline"},
                diagnostics=tuple(findings),
            )
        ids = problem.variables
        request = {
            "unknowns": [str(id) for id in ids],
            "rows": [
                {
                    "coefficients": [
                        row.residual.coefficients.get(id, 0) / scale for id in ids
                    ],
                    "constant": row.residual.constant / scale,
                    "relation": row.relation.value,
                }
                for row, scale in zip(problem.rows, scales, strict=True)
            ],
            "remaining": remaining,
            "iteration_limit": applied.iteration_limit,
            "options": dict(options),
        }
        environment = dict(os.environ)
        # Resolve the installed package root, not a repository-specific path. This
        # also makes workers work when callers import a source checkout via sys.path.
        package_root = str(Path(__file__).resolve().parents[3])
        environment["PYTHONPATH"] = os.pathsep.join(
            filter(None, (package_root, environment.get("PYTHONPATH")))
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "rangekeeper.execution.backends._worker"],
                input=json.dumps(request, allow_nan=False),
                text=True,
                capture_output=True,
                timeout=remaining,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return BackendResult(
                Termination.LIMITED,
                evidence={
                    "termination_condition": "worker_deadline",
                    "worker_budget_seconds": remaining,
                },
                diagnostics=tuple(findings),
            )
        if completed.returncode:
            raise NumericalError(
                f"solver worker exited {completed.returncode}: {completed.stderr[-2000:]}"
            )
        try:
            data = json.loads(completed.stdout)
            if data.get("unavailable"):
                raise BackendUnavailableError(data["unavailable"])
            if data.get("error"):
                raise NumericalError(data["error"])
            values = data.get("candidate")
            condition = data["termination"]
            return BackendResult(
                TERMINATIONS.get(condition, Termination.UNKNOWN),
                (
                    None
                    if values is None
                    else MappingProxyType(
                        {UUID(key): float(value) for key, value in values.items()}
                    )
                ),
                tuple(
                    Implementation.from_data(item) for item in data["implementations"]
                ),
                MappingProxyType(
                    {"termination_condition": condition, **data["evidence"]}
                ),
                tuple(findings),
                applied,
            )
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise NumericalError("invalid solver-worker response") from error

    @staticmethod
    def _scale(row: Row) -> float:
        """Return the divisor of one row, or raise UnsupportedError for its range.

        Only coefficients set the divisor, so that a large constant does not
        erase small coefficients.
        """
        coefficients = row.residual.coefficients.values()
        scale = max((1.0, *(abs(value) for value in coefficients)))
        if (
            any(abs(value / scale) <= SMALLEST_COEFFICIENT for value in coefficients)
            or abs(row.residual.constant / scale) >= LARGEST_CONSTANT
        ):
            raise UnsupportedError(
                "affine row exceeds the supported HiGHS numerical scaling range",
                document_id=row.assertion.document,
                targets=(row.assertion.constraint.id,),
            )
        return scale
