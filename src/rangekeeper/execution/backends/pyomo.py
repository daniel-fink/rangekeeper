"""Process-isolated Pyomo/HiGHS adapter with an enforced parent-side deadline."""

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

from rangekeeper.execution.backends.base import Result
from rangekeeper.execution.compiler import AffineProblem
from rangekeeper.execution.errors import (
    BackendUnavailableError,
    NumericalError,
    UnsupportedError,
)
from rangekeeper.execution.settings import Limits
from rangekeeper.schema.records import Implementation


class PyomoHighs:
    """Lower in a child process so a stalled native solver can be terminated.

    Only numerical rows cross the private JSON protocol; no solver object or
    mutable Model crosses it. Pyomo/highspy imports happen in the child. Timeout
    kills and reaps that process, discards partial output, and proves no infeasibility.

    ``options`` are HiGHS options. They replace the defaults of the worker, except
    for the options in ``RESERVED``, which the backend sets itself.
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
    ) -> Result:
        """Solve a compiled problem in a child process and return its Result."""
        refused = sorted(self.RESERVED.intersection(options))
        if refused:
            raise UnsupportedError(
                "the pyomo-highs backend sets these HiGHS options itself: "
                + ", ".join(refused)
            )
        if remaining <= 0:
            return Result("worker_deadline", evidence={"remaining_seconds": 0})
        ids = problem.binding.unknowns
        request = {
            "unknowns": [str(id) for id in ids],
            "rows": [
                {
                    "coefficients": [
                        row.residual.coefficients.get(id, 0) / row.scale for id in ids
                    ],
                    "constant": row.residual.constant / row.scale,
                    "relation": row.relation,
                }
                for row in problem.rows
            ],
            "remaining": remaining,
            "iteration_limit": limits.iteration_limit,
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
            return Result(
                "worker_deadline", evidence={"worker_budget_seconds": remaining}
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
            return Result(
                data["termination"],
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
                MappingProxyType(data["evidence"]),
            )
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise NumericalError("invalid solver-worker response") from error
