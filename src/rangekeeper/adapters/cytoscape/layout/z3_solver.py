"""Bounded integer reference model. Solver calls never write files.

Optimization uses incremental feasibility checks, retaining a checked incumbent
if the time budget expires. Each lexicographic phase advances only after proof.
"""

from dataclasses import asdict
from math import isfinite
from time import monotonic

from .check import check, metrics
from .model import Assembly, Node, Problem, Rect, grid_templates
from .reduction import collision_pairs
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
    hard, exclusions = [], []
    objects: list[Node | Assembly] = [*problem.nodes, *problem.assemblies]
    objects.sort(key=lambda o: o.id)
    variables = {
        o.id: z3.Ints(f"x_{j} y_{j} w_{j} h_{j}") for j, o in enumerate(objects)
    }
    for x, y, w, h in variables.values():
        hard.extend([
            x >= 0,
            y >= 0,
            w > 0,
            h > 0,
            x + w <= problem.width,
            y + h <= problem.height,
        ])
    for n in problem.nodes:
        _, _, w, h = variables[n.id]
        hard.extend([w == n.width, h == n.height])
    for i, px, py in problem.pins:
        x, y, _, _ = variables[i]
        hard.extend([x == px, y == py])

    def apart(a, b):
        x, y, w, h = a
        u, v, bw, bh = b
        return z3.Or(
            x + w + problem.gap <= u,
            u + bw + problem.gap <= x,
            y + h + problem.gap <= v,
            v + bh + problem.gap <= y,
        )

    obstacles = {n.id: variables[n.id] for n in problem.nodes}
    for a in problem.assemblies:
        x, y, w, h = variables[a.id]
        hard.extend([w >= a.min_width, h >= problem.header + 2 * problem.padding])
        for i in a.members:
            cx, cy, cw, ch = variables[i]
            hard.extend([
                cx >= x + problem.padding,
                cy >= y + problem.header + problem.padding,
                cx + cw <= x + w - problem.padding,
                cy + ch <= y + h - problem.padding,
            ])
        descendants = problem.descendants(a.id)
        for n in problem.nodes:
            if n.id not in descendants:
                exclusions.append(apart(variables[n.id], variables[a.id]))
        obstacles[a.id] = (x, y, w, problem.header)
    for outer in problem.assemblies:
        descendants = problem.descendants(outer.id)
        x, y, w, h = variables[outer.id]
        for inner in problem.assemblies:
            if inner.id == outer.id or inner.id in descendants:
                continue
            cx, cy, cw, ch = variables[inner.id]
            exclusions.append(z3.Or(cx < x, cy < y, cx + cw > x + w, cy + ch > y + h))
    strict_collisions = [
        apart(obstacles[i], obstacles[j]) for i, j in collision_pairs(problem)
    ]

    grid_vars, grid_costs, slot_vars, grid_scores = {}, [], {}, []
    for j, a in enumerate(sorted(problem.assemblies, key=lambda a: a.id)):
        templates = grid_templates(problem, a)
        if not templates:
            continue
        gx, gy, cols = z3.Ints(f"gx_{j} gy_{j} cols_{j}")
        grid_vars[a.id] = (gx, gy, cols)
        if problem.weights is not None:
            slots = {
                i: z3.Int(f"slot_{j}_{k}") for k, i in enumerate(sorted(a.members))
            }
            slot_vars[a.id] = slots
            hard.extend(z3.And(v >= 0, v < len(a.members)) for v in slots.values())
            hard.append(z3.Distinct(list(slots.values())))
        x, y, w, h = variables[a.id]
        hard.extend([
            cols >= 1,
            cols <= len(templates),
            gx >= x + problem.padding,
            gy >= y + problem.header + problem.padding,
            gx <= x + w - problem.padding,
            gy <= y + h - problem.padding,
        ])
        setting = next((v for v in problem.arrangements if v.assembly == a.id), None)
        if setting and setting.flow != "grid":
            vertical = setting.flow == "column"
            hard.append(cols == (1 if vertical else len(a.members)))
            start = (
                x + problem.padding
                if vertical
                else y + problem.header + problem.padding
            )
            span = (
                w - 2 * problem.padding
                if vertical
                else h - problem.header - 2 * problem.padding
            )
            for i in a.members:
                cx, cy, cw, ch = variables[i]
                size = cw if vertical else ch
                offset = {"start": 0, "center": (span - size) / 2, "end": span - size}[
                    setting.alignment
                ]
                hard.append((cx if vertical else cy) == start + offset)
            for i in a.members:
                for k in a.members:
                    if i == k:
                        continue
                    ci, cj = variables[i], variables[k]
                    hard.append(
                        z3.Implies(
                            slot_vars[a.id][i] < slot_vars[a.id][k],
                            (
                                (ci[1] + ci[3] + problem.gap <= cj[1])
                                if vertical
                                else (ci[0] + ci[2] + problem.gap <= cj[0])
                            ),
                        )
                    )
        pitch_x, pitch_y = z3.Ints(f"pitch_x_{j} pitch_y_{j}")
        for i in a.members:
            hard.extend([
                pitch_x >= variables[i][2] + problem.gap,
                pitch_y >= variables[i][3] + problem.gap,
            ])
        hard.extend([
            z3.Or([pitch_x == variables[i][2] + problem.gap for i in a.members]),
            z3.Or([pitch_y == variables[i][3] + problem.gap for i in a.members]),
        ])
        costs = []
        for c, template in enumerate(templates, 1):
            if problem.weights is not None:
                template = [
                    (i, slot_vars[a.id][i] % c, slot_vars[a.id][i] / c)
                    for i in a.members
                ]
            cost = z3.Sum([
                z3.Abs(variables[i][0] - gx - col * pitch_x)
                + z3.Abs(variables[i][1] - gy - row * pitch_y)
                for i, col, row in template
            ])
            costs.append(z3.If(cols == c, cost, 0))
        if setting and setting.spacing == "packed":
            vertical = setting.flow == "column"
            packed_costs = []
            for i in a.members:
                offset = z3.Sum([
                    z3.If(
                        slot_vars[a.id][k] < slot_vars[a.id][i],
                        variables[k][3 if vertical else 2] + problem.gap,
                        0,
                    )
                    for k in a.members
                ])
                target = (
                    y + problem.header + problem.padding
                    if vertical
                    else x + problem.padding
                ) + offset
                hard.append(variables[i][1 if vertical else 0] == target)
                packed_costs.append(
                    z3.Abs(variables[i][0] - gx - (0 if vertical else offset))
                    + z3.Abs(variables[i][1] - gy - (offset if vertical else 0))
                )
            costs = packed_costs
        local = z3.Sum(costs)
        grid_costs.append(local)
        strength = next(
            (p.strength for p in problem.preferences if p.assembly == a.id), 1
        )
        grid_scores.append(strength * (local / len(a.members)))
    right, bottom = z3.Ints("diagram_right diagram_bottom")
    hard.extend([right >= 0, bottom >= 0])
    for x, y, w, h in variables.values():
        hard.extend([right >= x + w, bottom >= y + h])
    # Equalities ensure measured extent equals the solver's value even before optimization.
    hard.extend([
        z3.Or([right == x + w for x, y, w, h in variables.values()]),
        z3.Or([bottom == y + h for x, y, w, h in variables.values()]),
    ])
    objective = [
        (
            "false_enclosures",
            (
                z3.Sum([z3.If(c, 0, 1) for c in exclusions])
                if exclusions
                else z3.IntVal(0)
            ),
        ),
        ("grid_displacement", z3.Sum(grid_costs) if grid_costs else z3.IntVal(0)),
        ("extent", right + bottom),
        (
            "assembly_extent",
            (
                z3.Sum([
                    variables[a.id][2] + variables[a.id][3] for a in problem.assemblies
                ])
                if problem.assemblies
                else z3.IntVal(0)
            ),
        ),
    ]
    score_expressions = {}
    if problem.weights is not None:

        def total(values):
            return z3.Sum(values) if values else z3.IntVal(0)

        def maximum(values):
            answer = values[0]
            for value in values[1:]:
                answer = z3.If(value > answer, value, answer)
            return answer

        groups = {a.id: a for a in problem.assemblies}
        directions, orders, affinities = [], [], []
        for p in problem.preferences:
            members = groups[p.assembly].members
            if len(members) > 1:
                w = grid_vars[p.assembly][2]
                h = total([
                    z3.If(w == c, (len(members) + c - 1) // c, 0)
                    for c in range(1, len(members) + 1)
                ])
                d = {
                    "unspecified": z3.IntVal(0),
                    "horizontal": z3.If(2 * h > w, 2 * h - w, 0),
                    "vertical": z3.If(2 * w > h, 2 * w - h, 0),
                    "balanced": z3.Abs(w - h),
                }[p.direction]
                directions.append(p.strength * problem.style_unit * d)
            penalties = []
            for before, after, axis in p.orders:
                a, b = variables[before], variables[after]
                coordinate = 0 if axis == "x" else 1
                deficit = (
                    2 * a[coordinate]
                    + a[coordinate + 2]
                    + 2
                    - 2 * b[coordinate]
                    - b[coordinate + 2]
                )
                penalties.append(z3.If(deficit > 0, deficit, 0))
            if penalties:
                denominator = 2 * len(penalties)
                rounding = denominator - 1 if problem.schema_version >= 3 else 0
                orders.append(
                    p.strength * ((total(penalties) + rounding) / denominator)
                )
            distances = []
            for left, other, weight in p.affinities:
                a, b = variables[left], variables[other]
                distances.append(
                    weight
                    * (
                        maximum([z3.IntVal(0), a[0] - b[0] - b[2], b[0] - a[0] - a[2]])
                        + maximum([
                            z3.IntVal(0),
                            a[1] - b[1] - b[3],
                            b[1] - a[1] - a[3],
                        ])
                    )
                )
            if distances:
                affinities.append(
                    p.strength * (total(distances) / sum(t[2] for t in p.affinities))
                )
        weights = problem.weights
        score_expressions = {
            "grid_score": total(grid_scores),
            "direction_score": total(directions),
            "order_score": total(orders),
            "similarity_score": total(affinities),
        }
        style = (
            weights.grid * score_expressions["grid_score"]
            + weights.direction * score_expressions["direction_score"]
            + weights.order * score_expressions["order_score"]
            + weights.similarity * score_expressions["similarity_score"]
            + weights.compactness * (right + bottom)
        )
        objective = [objective[0], ("style_cost", style), objective[-1]]
    solver = z3.Solver()
    solver.set(random_seed=0)
    if resource_limit:
        solver.set(rlimit=resource_limit)
    solver.add(*hard)
    solver.add(*strict_collisions)
    solver.add(*exclusions)
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
                for v, value in zip(variables[i], (r.x, r.y, r.width, r.height))
            )
        for i, vs in grid_vars.items():
            seed_constraints.extend(
                v == initial.grids[i][key] for v, key in zip(vs, ("x", "y", "columns"))
            )
        for i, slots in slot_vars.items():
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
        solver.add(*hard)
        solver.add(
            *(
                apart(obstacles[i], obstacles[j])
                for i, j in collision_pairs(problem, strict=False)
            )
        )
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
        for name, expr in objective:
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
            result.phases.append({
                "objective": name,
                "lower_bound": low,
                "value": high,
                "proven": low == high,
            })
            if low != high:
                break
            solver.add(expr == high)
        if len(result.phases) == len(objective) and all(
            p["proven"] for p in result.phases
        ):
            result.status = "optimal"
    result.incumbent_source = "solver"
    result.rectangles = {
        i: Rect(*(incumbent.eval(v).as_long() for v in vs))
        for i, vs in variables.items()
    }
    result.grids = {
        i: dict(zip(("x", "y", "columns"), (incumbent.eval(v).as_long() for v in vs)))
        for i, vs in grid_vars.items()
    }
    for i, slots in slot_vars.items():
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
    for name, expr in objective:
        if incumbent.eval(expr).as_long() != result.measurements[name]:
            raise RuntimeError(f"Solver/checker objective disagreement: {name}")
    for name, expr in score_expressions.items():
        if incumbent.eval(expr).as_long() != result.measurements[name]:
            raise RuntimeError(f"Solver/checker component disagreement: {name}")
    result.elapsed_seconds = monotonic() - start
    return result
