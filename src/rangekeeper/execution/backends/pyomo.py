"""Process-isolated Pyomo/HiGHS adapter with an enforced parent-side deadline."""

import json
import os
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType
from uuid import UUID

from ..._schema.records import Implementation
from ..compiler import Compiled
from ..settings import Limits
from ..errors import BackendUnavailable, NumericalError
from .base import Result


class PyomoHighs:
    """Lower in a child process so a stalled native solver can be terminated.

    Only numerical rows cross the private JSON protocol; no solver object or
    mutable Model crosses it. Pyomo/highspy imports happen in the child. Timeout
    kills and reaps that process, discards partial output, and proves no infeasibility.
    """

    def solve(self, problem: Compiled, *, limits: Limits, remaining: float) -> Result:
        if remaining <= 0:
            return Result("worker_deadline", evidence={"remaining_seconds": 0})
        ids = problem.prepared.unknowns
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
                raise BackendUnavailable(data["unavailable"])
            if data.get("error"):
                raise NumericalError(data["error"])
            values = data.get("candidate")
            return Result(
                data["termination"],
                (
                    None
                    if values is None
                    else MappingProxyType(
                        {key: float(value) for key, value in values.items()}
                    )
                ),
                tuple(
                    Implementation.from_data(item) for item in data["implementations"]
                ),
                MappingProxyType(data["evidence"]),
            )
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise NumericalError("invalid solver-worker response") from error
