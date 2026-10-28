"""Private numerical worker. Reads one request and writes one response on stdio."""

import importlib.metadata
import json
import sys
import time

from rangekeeper.shared.optional import requires


def solve(request):
    """Use public Pyomo interfaces and return observed versions, counts and status."""
    started = time.monotonic()
    # Record the installed versions; the package metadata declares the ranges.
    versions = {name: importlib.metadata.version(name) for name in ("pyomo", "highspy")}
    with requires("execution"):
        from pyomo.contrib.solver.common.results import SolutionStatus
        from pyomo.contrib.solver.solvers.highs import Highs
        from pyomo.environ import ConcreteModel, ConstraintList, Objective, Var, value

    size = len(request["unknowns"])
    model = ConcreteModel()
    model.variables = Var(range(size), initialize=0)
    # A fixed anchor keeps constant-only feasibility problems representable and
    # prevents Python from reducing a constant relation to an unsupported bool.
    model.anchor = Var(bounds=(0, 0), initialize=0)
    model.constraints = ConstraintList()
    model.constraints.add(model.anchor == 0)
    for row in request["rows"]:
        expression = sum(
            coefficient * model.variables[i]
            for i, coefficient in enumerate(row["coefficients"])
        )
        expression += row["constant"] + 0 * model.anchor
        if row["relation"] == "equal":
            model.constraints.add(expression == 0)
        elif row["relation"] == "less_than_or_equal":
            model.constraints.add(expression <= 0)
        else:
            model.constraints.add(expression >= 0)
    model.objective = Objective(
        expr=0 * model.anchor + sum(0 * model.variables[i] for i in range(size))
    )
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
        candidate = {
            id: float(value(model.variables[i]))
            for i, id in enumerate(request["unknowns"])
        }
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


def main():
    try:
        response = solve(json.load(sys.stdin))
    except ImportError as error:
        response = {"unavailable": str(error)}
    except importlib.metadata.PackageNotFoundError as error:
        response = {
            "unavailable": f"{error} is not installed. Install it with: "
            "pip install 'rangekeeper[execution]'"
        }
    except Exception as error:
        response = {"error": f"{type(error).__name__}: {error}"}
    print(json.dumps(response, allow_nan=False))


if __name__ == "__main__":
    main()
