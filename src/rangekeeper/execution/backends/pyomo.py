"""Process-isolated Pyomo/HiGHS adapter with an enforced parent-side deadline."""

import atexit
import json
import site
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

from rangekeeper.execution.backends._process import Workers
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
# The worker runs as a script, so that the isolated interpreter imports no
# Rangekeeper module and needs no package path.
_WORKER = Path(__file__).with_name("_worker.py")


def _command() -> tuple[str, ...]:
    """Return the command that starts a worker: this interpreter, in isolated mode.

    Isolated mode (``-I``) reads no ``PYTHON*`` environment variable and puts
    neither the current folder nor the user site directory on the import path.
    When this process reads its user site directory, the worker reads it too.
    """
    user = site.getusersitepackages() if site.ENABLE_USER_SITE else None
    sites = (user,) if user is not None and user in sys.path else ()
    return (sys.executable, "-I", str(_WORKER), *sites)


# One worker for each session: every solve reuses it, and it closes at exit.
_workers = Workers(_command)
atexit.register(_workers.close)


class PyomoHighs:
    """Solve in a worker process, so that a stalled native solver can be ended.

    Only numerical rows cross the private JSON protocol, as sparse rows: the
    nonzero coefficients of each row and their variable indices. No solver
    object or mutable Model crosses it. Pyomo and highspy load in the worker.

    The solves of one session reuse one worker, which starts with ``python -I``
    and closes at interpreter exit. Each solve builds a new Pyomo model and a new
    solver in it, so evidence and results are the same from a new worker or a
    reused one, in any order of solves. A solve that passes its deadline kills
    and reaps its worker, discards partial output, and proves no infeasibility.
    A worker that ends without a response gives a NumericalError with its exit
    code and the end of its stderr. The next solve after either starts a new
    worker.

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
        *,
        problem: AffineProblem,
        limits: Limits,
        remaining: float,
        options: Mapping[str, object] = MappingProxyType({}),
    ) -> BackendResult:
        """Solve a problem in the worker process and return its BackendResult."""
        deadline = time.monotonic() + remaining
        refused = sorted(self.RESERVED.intersection(options))
        if refused:
            raise UnsupportedError(
                "the pyomo-highs backend sets these HiGHS options itself: "
                + ", ".join(refused)
            )
        scales = tuple(self._scale(row) for row in problem.rows)
        applied, adjusted = _clamp(limits)
        findings = (_scaling(problem=problem, scales=scales), *adjusted)
        if remaining <= 0:
            return BackendResult(
                termination=Termination.LIMITED,
                evidence={"termination_condition": "worker_deadline"},
                diagnostics=findings,
            )
        request = _request(
            problem=problem, scales=scales, limits=applied, options=options
        )
        request["remaining"] = deadline - time.monotonic()
        text = json.dumps(request, allow_nan=False)
        with _workers.lease() as worker:
            line = worker.request(text, deadline=deadline)
            if line is None:
                return BackendResult(
                    termination=Termination.LIMITED,
                    evidence={
                        "termination_condition": "worker_deadline",
                        "worker_budget_seconds": remaining,
                    },
                    diagnostics=findings,
                )
            return _result(
                _response(line),
                variables=problem.variables,
                diagnostics=findings,
                limits=applied,
            )

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


def _scaling(*, problem: AffineProblem, scales: Sequence[float]) -> Diagnostic:
    """Return the diagnostic that gives each row's divisor and residual unit."""
    return Diagnostic(
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


def _clamp(limits: Limits) -> tuple[Limits, tuple[Diagnostic, ...]]:
    """Return the limits that HiGHS applies, and a diagnostic when they change."""
    if limits.iteration_limit <= ITERATION_MAXIMUM:
        return limits, ()
    return replace(limits, iteration_limit=ITERATION_MAXIMUM), (
        Diagnostic(
            severity=Severity.WARNING,
            code=Code.SETTINGS_ADJUSTED.value,
            message=f"iteration_limit clamped to HiGHS maximum {ITERATION_MAXIMUM}.",
            values={
                "settings": ["iteration_limit"],
                "disposition": "clamped",
                "effective": ITERATION_MAXIMUM,
            },
        ),
    )


def _request(
    *,
    problem: AffineProblem,
    scales: Sequence[float],
    limits: Limits,
    options: Mapping[str, object],
) -> dict[str, object]:
    """Return the worker request, with one sparse row for each scaled row.

    Each row lists its nonzero coefficients as ``[index, coefficient]`` pairs,
    in the order of the variables. The caller adds the remaining seconds.
    """
    index = {id: position for position, id in enumerate(problem.variables)}
    return {
        "size": len(problem.variables),
        "rows": [
            {
                "terms": sorted(
                    [index[id], coefficient / scale]
                    for id, coefficient in row.residual.coefficients.items()
                ),
                "constant": row.residual.constant / scale,
                "relation": row.relation.value,
            }
            for row, scale in zip(problem.rows, scales, strict=True)
        ],
        "iteration_limit": limits.iteration_limit,
        "options": dict(options),
    }


def _response(line: str) -> dict[str, object]:
    """Decode a response line; raise the error of a worker that could not solve."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError as error:
        raise NumericalError("invalid solver-worker response") from error
    if not isinstance(data, dict):
        raise NumericalError("invalid solver-worker response")
    if data.get("unavailable"):
        raise BackendUnavailableError(str(data["unavailable"]))
    if data.get("error"):
        raise NumericalError(str(data["error"]))
    return data


def _result(
    data: Mapping[str, object],
    *,
    variables: Sequence[UUID],
    diagnostics: tuple[Diagnostic, ...],
    limits: Limits,
) -> BackendResult:
    """Return the BackendResult of a decoded response; its candidate is by variable."""
    condition, evidence = data.get("termination"), data.get("evidence")
    values, implementations = data.get("candidate"), data.get("implementations")
    if not (
        isinstance(condition, str)
        and isinstance(evidence, dict)
        and isinstance(implementations, list)
        and (values is None or isinstance(values, list))
    ):
        raise NumericalError("invalid solver-worker response")
    try:
        return BackendResult(
            termination=TERMINATIONS.get(condition, Termination.UNKNOWN),
            candidate=(
                None
                if values is None
                else MappingProxyType(
                    {
                        id: float(value)
                        for id, value in zip(variables, values, strict=True)
                    }
                )
            ),
            implementations=tuple(
                Implementation.from_data(item) for item in implementations
            ),
            evidence=MappingProxyType({"termination_condition": condition, **evidence}),
            diagnostics=diagnostics,
            limits=limits,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise NumericalError("invalid solver-worker response") from error
