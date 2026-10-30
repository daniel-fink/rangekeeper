"""Private numerical worker: it answers solve requests until its input ends.

The parent starts it as ``python -I _worker.py [site directory ...]`` and keeps
it for the solves of its session (``pyomo.PyomoHighs``). Each line on stdin is
one JSON request; the worker writes one JSON response line for each, in order.
The responses go to a private copy of stdout, and stdout itself goes to stderr,
so that a message from the solver cannot break the protocol.

At start the worker imports only the standard library. Pyomo and highspy load on
the first request. So the worker imports no Rangekeeper module, and the isolated
interpreter needs no package path. Each request builds a new Pyomo model and a
new solver, so a response does not depend on the requests before it.

A request has the ``size`` of the problem (its number of variables) and its
sparse ``rows``: each row has ``terms``, the ``[index, coefficient]`` pairs of
its nonzero coefficients, a ``constant`` and a ``relation``. The candidate in
the response lists one value for each variable, in index order.
"""

import importlib.metadata
import json
import operator
import os
import signal
import site
import sys
import time
from collections.abc import Callable, Iterable
from typing import IO, Any

# The packages whose installed versions the evidence records.
PACKAGES = ("pyomo", "highspy")
# How each row's expression relates to zero.
RELATIONS: dict[str, Callable[[Any, int], Any]] = {
    "equal": operator.eq,
    "less_than_or_equal": operator.le,
    "greater_than_or_equal": operator.ge,
}


def build(request: dict[str, Any]) -> Any:
    """Return the Pyomo model of a request: its variables, an anchor and its rows."""
    from pyomo.environ import (  # noqa: PLC0415 - optional dependency
        ConcreteModel,
        ConstraintList,
        Objective,
        Var,
    )

    size = request["size"]
    model = ConcreteModel()
    model.variables = Var(range(size), initialize=0)
    # A fixed anchor keeps constant-only feasibility problems representable and
    # prevents Python from reducing a constant relation to an unsupported bool.
    model.anchor = Var(bounds=(0, 0), initialize=0)
    model.constraints = ConstraintList()
    # Pyomo gives HiGHS the variables in the order in which the constraints
    # name them. The first constraint names each one, so that the columns are
    # in index order whatever the rows. HiGHS drops the zero coefficients.
    model.constraints.add(
        model.anchor + sum(0 * model.variables[i] for i in range(size)) == 0
    )
    for row in request["rows"]:
        expression = sum(
            coefficient * model.variables[index] for index, coefficient in row["terms"]
        )
        expression += row["constant"] + 0 * model.anchor
        model.constraints.add(RELATIONS[row["relation"]](expression, 0))
    # The objective names every variable, so that HiGHS receives each one.
    model.objective = Objective(
        expr=0 * model.anchor + sum(0 * model.variables[i] for i in range(size))
    )
    return model


def solve(request: dict[str, Any]) -> dict[str, Any]:
    """Use public Pyomo interfaces and return observed versions, counts and status."""
    started = time.monotonic()
    # Record the installed versions; the package metadata declares the ranges.
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    from pyomo.contrib.solver.common.results import (  # noqa: PLC0415 - optional dependency
        SolutionStatus,
    )
    from pyomo.contrib.solver.solvers.highs import Highs  # noqa: PLC0415 - optional dependency
    from pyomo.environ import value  # noqa: PLC0415 - optional dependency

    model = build(request)
    options = {
        "solver": "simplex",
        "presolve": "on",
        "parallel": "off",
        "random_seed": 0,
        "simplex_iteration_limit": request["iteration_limit"],
        "small_matrix_value": 1e-12,
        "primal_feasibility_tolerance": 1e-7,
        "dual_feasibility_tolerance": 1e-7,
        "output_flag": False,
    }
    options.update(request.get("options") or {})
    remaining = max(1e-9, request["remaining"] - (time.monotonic() - started))
    result = Highs().solve(
        model,
        load_solutions=False,
        raise_exception_on_nonoptimal_result=False,
        time_limit=remaining,
        threads=1,
        solver_options=options,
    )
    candidate = None
    if result.solution_status in (SolutionStatus.optimal, SolutionStatus.feasible):
        result.solution_loader.load_solution()
        candidate = [float(value(model.variables[i])) for i in range(request["size"])]
    return {
        "termination": result.termination_condition.name,
        "candidate": candidate,
        "implementations": [
            {"kind": "compiler", "name": "Pyomo", "version": versions["pyomo"]},
            {
                "kind": "solver",
                "name": "HiGHS",
                "version": ".".join(map(str, result.solver_version)),
            },
        ],
        "evidence": {
            "solution_status": result.solution_status.name,
            "simplex_iterations": getattr(
                result.extra_info, "simplex_iteration_count", None
            ),
            "highs_seconds": result.timing_info.highs_time,
            "worker_seconds": time.monotonic() - started,
            "solver_time_limit": remaining,
            "solver_options": options,
            "threads": 1,
            "package_versions": versions,
        },
    }


def respond(line: str) -> str:
    """Return the response line to one request line; a failure is a response too."""
    try:
        return json.dumps(solve(json.loads(line)), allow_nan=False)
    except ImportError as error:
        # The same hint as rangekeeper.shared.optional.requires. A missing
        # distribution is a PackageNotFoundError, whose name is the package.
        package = (error.name or "A dependency").partition(".")[0]
        hint = f"{package} is not installed. Install it with: pip install 'rangekeeper[execution]'"
        return json.dumps({"unavailable": hint})
    except Exception as error:
        return json.dumps({"error": f"{type(error).__name__}: {error}"})


def serve(*, requests: Iterable[str], responses: IO[str]) -> None:
    """Write one response line for each request line, in order, until the input ends."""
    for line in requests:
        responses.write(respond(line) + "\n")
        responses.flush()


def main() -> None:
    """Serve the requests on stdin. The parent owns the lifetime of the worker.

    The arguments are site directories of the parent, such as its user site
    directory, which isolated mode does not read.
    """
    # An interrupt in the terminal reaches the whole process group; the parent
    # decides whether this worker ends.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    for directory in sys.argv[1:]:
        site.addsitedir(directory)
    responses = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    serve(requests=sys.stdin, responses=responses)


if __name__ == "__main__":
    main()
