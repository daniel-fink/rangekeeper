"""Optional bounded local refinement; always returns globally checked geometry.

Neighborhood proofs are never reported as global optimality. All full-problem
constraints and scores remain present; objects outside a neighborhood are fixed.
"""

from copy import deepcopy
from math import isfinite
from time import monotonic

from .check import check, metrics
from .minizinc_solver import solve
from .model import Problem
from .result import Result


def refine(
    problem: Problem,
    initial: Result,
    *,
    time_limit=20,
    region_limit=6,
    max_regions=3,
    executable=None,
):
    if (
        any(not isfinite(v) or v <= 0 for v in (time_limit, region_limit))
        or type(max_regions) is not int
        or max_regions < 1
    ):
        raise ValueError("Positive finite budgets and positive max_regions required")
    if (
        problem.weights is None
        or initial.problem_fingerprint != problem.fingerprint
        or check(problem, initial.rectangles)
    ):
        raise ValueError(
            "Refinement needs preference weights and a matching checked strict seed"
        )
    start = monotonic()
    deadline = start + time_limit
    result = deepcopy(initial)
    result.measurements = metrics(problem, result.rectangles, result.grids)
    result.status = "feasible"
    result.strict_status = "sat"
    result.mode = "strict"
    result.findings = []
    result.phases = []
    result.solver_statistics = []
    result.first_solution_seconds = None
    result.build_seconds = 0
    result.incumbent_source = "checked_seed"
    nodes = {n.id for n in problem.nodes}
    weights = problem.weights
    details = result.measurements["preference_details"]

    def priority(a):
        d = details.get(a.id, {})
        return (
            -d.get("strength", 1)
            * (
                weights.direction * d.get("direction", 0)
                + weights.order * d.get("order", 0)
                + weights.similarity * d.get("similarity", 0)
            ),
            a.id,
        )

    regions = sorted(
        (
            a
            for a in problem.assemblies
            if len(a.members) > 1 and set(a.members) <= nodes
        ),
        key=priority,
    )[:max_regions]
    for assembly in regions:
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        before = (
            result.measurements["style_cost"],
            result.measurements["assembly_extent"],
        )
        phase_start = monotonic()
        attempt = solve(
            problem,
            initial=result,
            time_limit=min(region_limit, remaining),
            neighborhood=assembly.members,
            executable=executable,
        )
        after = (
            attempt.measurements["style_cost"],
            attempt.measurements["assembly_extent"],
        )
        accepted = after < before
        result.solver_statistics.append(
            {
                "assembly": assembly.id,
                "movable_objects": list(assembly.members),
                "before": list(before),
                "after": list(after),
                "accepted": accepted,
                "wall_seconds": monotonic() - phase_start,
                "native_first_seconds": attempt.first_solution_seconds,
                "phases": attempt.phases,
                "statistics": attempt.solver_statistics,
            }
        )
        result.build_seconds += attempt.build_seconds
        result.solver_version = attempt.solver_version
        if accepted:
            result.rectangles = attempt.rectangles
            result.grids = attempt.grids
            result.measurements = attempt.measurements
            result.incumbent_source = "neighborhood_solver"
    result.search_scope = {
        "mode": "bounded_neighborhoods",
        "max_regions": max_regions,
        "seconds_per_region": region_limit,
    }
    result.reason = "Bounded local refinement; no global optimum claimed"
    result.elapsed_seconds = monotonic() - start
    return result
