"""Bounded integer reference model. Solver calls never write files.

Optimization uses incremental feasibility checks, retaining a checked incumbent
if the time budget expires. Each lexicographic phase advances only after proof.
"""

from dataclasses import asdict
from math import isfinite
from time import monotonic

from .check import check, metrics
from .model import Problem, Rect
from .z3_model import Formulation
from .result import Result


def solve(
    problem: Problem,
    *,
    time_limit: float = 10,
    optimize: bool = True,
    allow_relaxed: bool = False,
    resource_limit: int | None = None,
    initial: Result | None = None,
) -> Result:
    if not isfinite(time_limit) or time_limit <= 0:
        raise ValueError("time_limit must be positive and finite")
    if resource_limit is not None and (
        type(resource_limit) is not int or resource_limit <= 0
    ):
        raise ValueError("resource_limit must be a positive integer")
    import z3  # Optional dependency; contract/checker import without Z3.

    start = monotonic()
    deadline = start + time_limit
    formulation = Formulation(problem)
    solver = z3.Solver()
    solver.set(random_seed=0)
    if resource_limit:
        solver.set(rlimit=resource_limit)
    solver.add(*formulation.hard)
    solver.add(*formulation.strict_collisions)
    solver.add(*formulation.exclusions)
    result = Result(
        "unknown",
        "unknown",
        solver_version=z3.get_version_string(),
        problem_fingerprint=problem.fingerprint,
        build_seconds=monotonic() - start,
    )

    def run(assumptions=()):
        remaining = deadline - monotonic()
        if remaining <= 0:
            result.reason = "Time budget exhausted"
            return z3.unknown
        solver.set(timeout=max(1, int(remaining * 1000)))
        state = solver.check(*assumptions)
        if state == z3.unknown:
            result.reason = solver.reason_unknown()
        return state

    if initial is not None:
        if initial.problem_fingerprint != problem.fingerprint or check(
            problem, initial.rectangles
        ):
            raise ValueError(
                "Initial geometry must match the problem and pass strict checking"
            )
        metrics(problem, initial.rectangles, initial.grids)
        # Assumptions are scoped to this timed check. push() before the first
        # check can trigger unbounded preprocessing on the unconstrained model.
        seed_constraints: list[z3.BoolRef] = []
        for i, r in initial.rectangles.items():
            seed_constraints.extend(
                v == value
                for v, value in zip(
                    formulation.variables[i], (r.x, r.y, r.width, r.height)
                )
            )
        for i, vs in formulation.grid_vars.items():
            seed_constraints.extend(
                v == initial.grids[i][key] for v, key in zip(vs, ("x", "y", "columns"))
            )
        for i, slots in formulation.slot_vars.items():
            seed_constraints.extend(
                v == initial.grids[i]["slots"][member] for member, v in slots.items()
            )
        state = run(seed_constraints)
        seed_model = solver.model() if state == z3.sat else None
        if state == z3.unsat:
            raise RuntimeError(
                "Checked initial geometry disagrees with solver constraints"
            )
    else:
        state = run()
        seed_model = None
    result.strict_status = str(state)
    if state == z3.unsat and allow_relaxed:
        result.mode = "diagnostic"
        solver.reset()
        solver.set(random_seed=0)
        if resource_limit:
            solver.set(rlimit=resource_limit)
        solver.add(*formulation.hard)
        solver.add(*formulation.relaxed)
        state = run()
    if state != z3.sat:
        result.status = "infeasible" if state == z3.unsat else "unknown"
        if state == z3.unsat:
            result.reason = (
                "Infeasible within the supplied canvas, dimensions, spacing and pins"
            )
        result.elapsed_seconds = monotonic() - start
        return result
    result.first_solution_seconds = monotonic() - start
    incumbent = seed_model if seed_model is not None else solver.model()
    result.status = "feasible"
    if optimize:
        for name, expr in formulation.objective:
            low, high = 0, incumbent.eval(expr).as_long()
            if name == "false_enclosures" and result.strict_status == "unsat":
                low = 1
            while low < high:
                middle = (low + high) // 2
                solver.push()
                solver.add(expr <= middle)
                state = run()
                if state == z3.sat:
                    incumbent = solver.model()
                    high = incumbent.eval(expr).as_long()
                elif state == z3.unsat:
                    low = middle + 1
                solver.pop()
                if state == z3.unknown:
                    break
            result.phases.append(
                {
                    "objective": name,
                    "lower_bound": low,
                    "value": high,
                    "proven": low == high,
                }
            )
            if low != high:
                break
            solver.add(expr == high)
        if len(result.phases) == len(formulation.objective) and all(
            p["proven"] for p in result.phases
        ):
            result.status = "optimal"
    result.incumbent_source = "solver"
    result.rectangles = {
        i: Rect(*(incumbent.eval(v).as_long() for v in vs))
        for i, vs in formulation.variables.items()
    }
    result.grids = {
        i: dict(zip(("x", "y", "columns"), (incumbent.eval(v).as_long() for v in vs)))
        for i, vs in formulation.grid_vars.items()
    }
    for i, slots in formulation.slot_vars.items():
        result.grids[i]["slots"] = {
            member: incumbent.eval(v).as_long() for member, v in slots.items()
        }
    findings = check(problem, result.rectangles)
    unexpected = [
        f for f in findings if f.code != "exclusion" or result.mode == "strict"
    ]
    if unexpected:
        raise RuntimeError(
            f"Solver result failed independent geometry check: {unexpected}"
        )
    result.findings = [asdict(f) for f in findings]
    result.measurements = metrics(problem, result.rectangles, result.grids)
    for name, expr in formulation.objective:
        if incumbent.eval(expr).as_long() != result.measurements[name]:
            raise RuntimeError(f"Solver/checker objective disagreement: {name}")
    for name, expr in formulation.score_expressions.items():
        if incumbent.eval(expr).as_long() != result.measurements[name]:
            raise RuntimeError(f"Solver/checker component disagreement: {name}")
    result.elapsed_seconds = monotonic() - start
    return result
