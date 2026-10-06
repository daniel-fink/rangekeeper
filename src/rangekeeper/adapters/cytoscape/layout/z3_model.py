"""Build Z3 geometry and preferences without running a solver.

The formulation owns symbolic state. The independent checker owns arithmetic
acceptance so formulation mistakes cannot certify their own output.
"""

from typing import Any

from .model import Assembly, Node, Problem, grid_templates
from .reduction import collision_pairs


class Formulation:
    """Compose geometry, grid placement and ordered objectives for one Problem."""

    def __init__(self, problem: Problem) -> None:
        import z3

        self.z3, self.problem = z3, problem
        self.geometry()
        self.grids()
        self.extent()
        self.preferences()
        self.relaxed = [
            self.apart(self.obstacles[i], self.obstacles[j])
            for i, j in collision_pairs(problem, strict=False)
        ]

    def apart(self, a, b):
        """Express separation with the declared gap."""
        problem = self.problem
        z3 = self.z3
        x, y, w, h = a
        u, v, bw, bh = b
        return z3.Or(
            x + w + problem.gap <= u,
            u + bw + problem.gap <= x,
            y + h + problem.gap <= v,
            v + bh + problem.gap <= y,
        )

    def geometry(self) -> None:
        """Constrain bounds, membership, pins and strict exclusions."""
        problem, z3 = self.problem, self.z3
        self.hard: list[Any] = []
        self.exclusions: list[Any] = []
        objects: list[Node | Assembly] = [*problem.nodes, *problem.assemblies]
        objects.sort(key=lambda o: o.id)
        self.variables = {
            o.id: z3.Ints(f"x_{j} y_{j} w_{j} h_{j}") for j, o in enumerate(objects)
        }
        for x, y, w, h in self.variables.values():
            self.hard.extend(
                [
                    x >= 0,
                    y >= 0,
                    w > 0,
                    h > 0,
                    x + w <= problem.width,
                    y + h <= problem.height,
                ]
            )
        for n in problem.nodes:
            _, _, w, h = self.variables[n.id]
            self.hard.extend([w == n.width, h == n.height])
        for i, px, py in problem.pins:
            x, y, _, _ = self.variables[i]
            self.hard.extend([x == px, y == py])

        self.obstacles = {n.id: self.variables[n.id] for n in problem.nodes}
        for a in problem.assemblies:
            x, y, w, h = self.variables[a.id]
            self.hard.extend(
                [w >= a.min_width, h >= problem.header + 2 * problem.padding]
            )
            for i in a.members:
                cx, cy, cw, ch = self.variables[i]
                self.hard.extend(
                    [
                        cx >= x + problem.padding,
                        cy >= y + problem.header + problem.padding,
                        cx + cw <= x + w - problem.padding,
                        cy + ch <= y + h - problem.padding,
                    ]
                )
            descendants = problem.descendants(a.id)
            for n in problem.nodes:
                if n.id not in descendants:
                    self.exclusions.append(
                        self.apart(self.variables[n.id], self.variables[a.id])
                    )
            self.obstacles[a.id] = (x, y, w, problem.header)
        for outer in problem.assemblies:
            descendants = problem.descendants(outer.id)
            x, y, w, h = self.variables[outer.id]
            for inner in problem.assemblies:
                if inner.id == outer.id or inner.id in descendants:
                    continue
                cx, cy, cw, ch = self.variables[inner.id]
                self.exclusions.append(
                    z3.Or(cx < x, cy < y, cx + cw > x + w, cy + ch > y + h)
                )
        self.strict_collisions = [
            self.apart(self.obstacles[i], self.obstacles[j])
            for i, j in collision_pairs(problem)
        ]

    def grids(self) -> None:
        """Constrain member slots and grid or packed arrangements."""
        problem, z3 = self.problem, self.z3
        self.grid_vars, self.grid_costs, self.slot_vars, self.grid_scores = (
            {},
            [],
            {},
            [],
        )
        for j, a in enumerate(sorted(problem.assemblies, key=lambda a: a.id)):
            templates = grid_templates(problem, a)
            if not templates:
                continue
            gx, gy, cols = z3.Ints(f"gx_{j} gy_{j} cols_{j}")
            self.grid_vars[a.id] = (gx, gy, cols)
            if problem.weights is not None:
                slots = {
                    i: z3.Int(f"slot_{j}_{k}") for k, i in enumerate(sorted(a.members))
                }
                self.slot_vars[a.id] = slots
                self.hard.extend(
                    z3.And(v >= 0, v < len(a.members)) for v in slots.values()
                )
                self.hard.append(z3.Distinct(list(slots.values())))
            x, y, w, h = self.variables[a.id]
            self.hard.extend(
                [
                    cols >= 1,
                    cols <= len(templates),
                    gx >= x + problem.padding,
                    gy >= y + problem.header + problem.padding,
                    gx <= x + w - problem.padding,
                    gy <= y + h - problem.padding,
                ]
            )
            setting = next(
                (v for v in problem.arrangements if v.assembly == a.id), None
            )
            if setting and setting.flow != "grid":
                vertical = setting.flow == "column"
                self.hard.append(cols == (1 if vertical else len(a.members)))
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
                    cx, cy, cw, ch = self.variables[i]
                    size = cw if vertical else ch
                    offset = {
                        "start": 0,
                        "center": (span - size) / 2,
                        "end": span - size,
                    }[setting.alignment]
                    self.hard.append((cx if vertical else cy) == start + offset)
                for i in a.members:
                    for k in a.members:
                        if i == k:
                            continue
                        ci, cj = self.variables[i], self.variables[k]
                        self.hard.append(
                            z3.Implies(
                                self.slot_vars[a.id][i] < self.slot_vars[a.id][k],
                                (
                                    (ci[1] + ci[3] + problem.gap <= cj[1])
                                    if vertical
                                    else (ci[0] + ci[2] + problem.gap <= cj[0])
                                ),
                            )
                        )
            pitch_x, pitch_y = z3.Ints(f"pitch_x_{j} pitch_y_{j}")
            for i in a.members:
                self.hard.extend(
                    [
                        pitch_x >= self.variables[i][2] + problem.gap,
                        pitch_y >= self.variables[i][3] + problem.gap,
                    ]
                )
            self.hard.extend(
                [
                    z3.Or(
                        [
                            pitch_x == self.variables[i][2] + problem.gap
                            for i in a.members
                        ]
                    ),
                    z3.Or(
                        [
                            pitch_y == self.variables[i][3] + problem.gap
                            for i in a.members
                        ]
                    ),
                ]
            )
            costs = []
            for c, template in enumerate(templates, 1):
                if problem.weights is not None:
                    template = [
                        (i, self.slot_vars[a.id][i] % c, self.slot_vars[a.id][i] / c)
                        for i in a.members
                    ]
                cost = z3.Sum(
                    [
                        z3.Abs(self.variables[i][0] - gx - col * pitch_x)
                        + z3.Abs(self.variables[i][1] - gy - row * pitch_y)
                        for i, col, row in template
                    ]
                )
                costs.append(z3.If(cols == c, cost, 0))
            if setting and setting.spacing == "packed":
                vertical = setting.flow == "column"
                packed_costs = []
                for i in a.members:
                    offset = z3.Sum(
                        [
                            z3.If(
                                self.slot_vars[a.id][k] < self.slot_vars[a.id][i],
                                self.variables[k][3 if vertical else 2] + problem.gap,
                                0,
                            )
                            for k in a.members
                        ]
                    )
                    target = (
                        y + problem.header + problem.padding
                        if vertical
                        else x + problem.padding
                    ) + offset
                    self.hard.append(self.variables[i][1 if vertical else 0] == target)
                    packed_costs.append(
                        z3.Abs(self.variables[i][0] - gx - (0 if vertical else offset))
                        + z3.Abs(
                            self.variables[i][1] - gy - (offset if vertical else 0)
                        )
                    )
                costs = packed_costs
            local = z3.Sum(costs)
            self.grid_costs.append(local)
            strength = next(
                (p.strength for p in problem.preferences if p.assembly == a.id), 1
            )
            self.grid_scores.append(strength * (local / len(a.members)))

    def extent(self) -> None:
        """Match canvas extent exactly, including before optimization."""
        problem, z3 = self.problem, self.z3
        self.right, self.bottom = z3.Ints("diagram_right diagram_bottom")
        self.hard.extend([self.right >= 0, self.bottom >= 0])
        for x, y, w, h in self.variables.values():
            self.hard.extend([self.right >= x + w, self.bottom >= y + h])
        # Equalities ensure measured extent equals the solver's value even before optimization.
        self.hard.extend(
            [
                z3.Or([self.right == x + w for x, y, w, h in self.variables.values()]),
                z3.Or([self.bottom == y + h for x, y, w, h in self.variables.values()]),
            ]
        )
        self.objective = [
            (
                "false_enclosures",
                (
                    z3.Sum([z3.If(c, 0, 1) for c in self.exclusions])
                    if self.exclusions
                    else z3.IntVal(0)
                ),
            ),
            (
                "grid_displacement",
                z3.Sum(self.grid_costs) if self.grid_costs else z3.IntVal(0),
            ),
            ("extent", self.right + self.bottom),
            (
                "assembly_extent",
                (
                    z3.Sum(
                        [
                            self.variables[a.id][2] + self.variables[a.id][3]
                            for a in problem.assemblies
                        ]
                    )
                    if problem.assemblies
                    else z3.IntVal(0)
                ),
            ),
        ]

    def preferences(self) -> None:
        """Build optional weighted preferences without weakening hard rules."""
        problem, z3 = self.problem, self.z3
        self.score_expressions: dict[str, Any] = {}
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
                    w = self.grid_vars[p.assembly][2]
                    h = total(
                        [
                            z3.If(w == c, (len(members) + c - 1) // c, 0)
                            for c in range(1, len(members) + 1)
                        ]
                    )
                    d = {
                        "unspecified": z3.IntVal(0),
                        "horizontal": z3.If(2 * h > w, 2 * h - w, 0),
                        "vertical": z3.If(2 * w > h, 2 * w - h, 0),
                        "balanced": z3.Abs(w - h),
                    }[p.direction]
                    directions.append(p.strength * problem.style_unit * d)
                penalties = []
                for before, after, axis in p.orders:
                    a, b = self.variables[before], self.variables[after]
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
                    a, b = self.variables[left], self.variables[other]
                    distances.append(
                        weight
                        * (
                            maximum(
                                [z3.IntVal(0), a[0] - b[0] - b[2], b[0] - a[0] - a[2]]
                            )
                            + maximum(
                                [
                                    z3.IntVal(0),
                                    a[1] - b[1] - b[3],
                                    b[1] - a[1] - a[3],
                                ]
                            )
                        )
                    )
                if distances:
                    affinities.append(
                        p.strength
                        * (total(distances) / sum(t[2] for t in p.affinities))
                    )
            weights = problem.weights
            self.score_expressions = {
                "grid_score": total(self.grid_scores),
                "direction_score": total(directions),
                "order_score": total(orders),
                "similarity_score": total(affinities),
            }
            style = (
                weights.grid * self.score_expressions["grid_score"]
                + weights.direction * self.score_expressions["direction_score"]
                + weights.order * self.score_expressions["order_score"]
                + weights.similarity * self.score_expressions["similarity_score"]
                + weights.compactness * (self.right + self.bottom)
            )
            self.objective = [
                self.objective[0],
                ("style_cost", style),
                self.objective[-1],
            ]
