"""Checked recursive-grid incumbent for tree fixtures, never a solver constraint.

Shared memberships and pins deliberately return no seed. Every solver may use
the same saved incumbent. Candidate ordering and packing are heuristic, not an
optimum or an interpretation of physical order.
"""

from rangekeeper.adapters.cytoscape.layout.model import (
    ArrangementFlow,
    ArrangementSpacing,
)
from rangekeeper.adapters.cytoscape.layout.result import ResultStatus, StrictStatus
from dataclasses import replace

from rangekeeper.adapters.cytoscape.layout.check import assess, metrics
from rangekeeper.adapters.cytoscape.layout.model import Assembly, Node, Problem, Rect
from rangekeeper.adapters.cytoscape.layout.result import Result


def grid_seed(problem: Problem) -> Result | None:
    if problem.weights is None or problem.pins:
        return None
    all_objects: tuple[Node | Assembly, ...] = (*problem.nodes, *problem.assemblies)
    objects = {o.id: o for o in all_objects}
    nodes = {n.id: n for n in problem.nodes}
    groups = {a.id: a for a in problem.assemblies}
    preferences = {p.assembly: p for p in problem.preferences}
    arrangements = {a.assembly: a for a in problem.arrangements}
    parents = {i: 0 for i in objects}
    for a in problem.assemblies:
        for i in a.members:
            parents[i] += 1
    roots = [i for i, n in parents.items() if n == 0]
    if len(roots) != 1 or any(n > 1 for n in parents.values()):
        return None

    def build(identifier):
        if identifier not in groups:
            n = nodes[identifier]
            return {identifier: Rect(0, 0, n.width, n.height)}, {}
        a = groups[identifier]
        if not a.members:
            return {
                identifier: Rect(
                    0, 0, a.min_width, problem.header + 2 * problem.padding
                )
            }, {}
        children = {i: build(i) for i in a.members}
        if any(v is None for v in children.values()):
            return None
        ids = tuple(sorted(a.members))
        orders = {ids}
        p = preferences.get(identifier)
        setting = arrangements.get(identifier)
        if p:
            affinity = {frozenset((i, j)): w for i, j, w in p.affinities}
            for first in ids if affinity else ():
                path = [first]
                remaining = set(ids) - {first}
                while remaining:
                    nxt = min(
                        remaining,
                        key=lambda i: (-affinity.get(frozenset((path[-1], i)), 0), i),
                    )
                    remaining.remove(nxt)
                    path.append(nxt)
                orders.add(tuple(path))
            if p.orders:
                before = {(i, j) for i, j, _axis in p.orders}
                path, remaining = [], set(ids)
                while remaining:
                    ready = sorted(
                        i
                        for i in remaining
                        if not any(j == i and k in remaining for k, j in before)
                    )
                    if not ready:
                        break  # Contradictory wishes stay soft; no feasibility claim.
                    path.append(ready[0])
                    remaining.remove(ready[0])
                if not remaining:
                    orders.add(tuple(path))
        included = {identifier} | set().union(*(set(v[0]) for v in children.values()))
        local_problem = replace(
            problem,
            nodes=tuple(n for n in problem.nodes if n.id in included),
            assemblies=tuple(g for g in problem.assemblies if g.id in included),
            arrangements=tuple(
                v for v in problem.arrangements if v.assembly in included
            ),
            preferences=tuple(
                pref for pref in problem.preferences if pref.assembly in included
            ),
        )
        pitch_x = max(children[i][0][i].width for i in ids) + problem.gap
        pitch_y = max(children[i][0][i].height for i in ids) + problem.gap
        candidates = []
        layouts = set()
        for order in sorted(orders):
            columns = range(1, len(ids) + 1)
            if setting and setting.flow != ArrangementFlow.GRID:
                columns = [1 if setting.flow == ArrangementFlow.COLUMN else len(ids)]
            for cols in columns:
                slots = list(range(len(ids)))
                traversals = [slots]
                if p and p.affinities:
                    traversals += [
                        sorted(slots, key=lambda k: (k % cols, k // cols)),
                        sorted(
                            slots,
                            key=lambda k: (
                                k // cols,
                                k % cols if (k // cols) % 2 == 0 else -(k % cols),
                            ),
                        ),
                    ]
                for traversal in traversals:
                    placed = dict(zip(traversal, order))
                    layouts.add((tuple(placed[k] for k in slots), cols))
        for order, cols in sorted(layouts):
            rectangles, grids = {}, {}
            for rank, child in enumerate(order):
                dx = problem.padding + (rank % cols) * pitch_x
                dy = problem.header + problem.padding + (rank // cols) * pitch_y
                if setting and setting.flow != ArrangementFlow.GRID:
                    vertical = setting.flow == ArrangementFlow.COLUMN
                    cross_span = (
                        max(a.min_width - 2 * problem.padding, pitch_x - problem.gap)
                        if vertical
                        else pitch_y - problem.gap
                    )
                    child_rect = children[child][0][child]
                    size = child_rect.width if vertical else child_rect.height
                    offset = {
                        "start": 0,
                        "center": (cross_span - size) // 2,
                        "end": cross_span - size,
                    }[setting.alignment.value]
                    if vertical:
                        dx += offset
                    else:
                        dy += offset
                if setting and setting.spacing == ArrangementSpacing.PACKED:
                    if setting.flow == ArrangementFlow.COLUMN:
                        dy = (
                            problem.header
                            + problem.padding
                            + sum(
                                children[i][0][i].height + problem.gap
                                for i in order[:rank]
                            )
                        )
                    else:
                        dx = problem.padding + sum(
                            children[i][0][i].width + problem.gap for i in order[:rank]
                        )
                coords, witnesses = children[child]
                rectangles.update(
                    {i: replace(r, x=r.x + dx, y=r.y + dy) for i, r in coords.items()}
                )
                grids.update(
                    {
                        i: {**g, "x": g["x"] + dx, "y": g["y"] + dy}
                        for i, g in witnesses.items()
                    }
                )
            width = max(
                a.min_width,
                max(r.right for r in rectangles.values()) + problem.padding,
            )
            height = max(r.bottom for r in rectangles.values()) + problem.padding
            if width > problem.width or height > problem.height:
                continue
            rectangles[identifier] = Rect(0, 0, width, height)
            grids[identifier] = {
                "x": problem.padding,
                "y": problem.header + problem.padding,
                "columns": cols,
                "slots": {i: j for j, i in enumerate(order)},
            }
            score = metrics(local_problem, rectangles, grids)
            candidates.append(
                (
                    score["style_cost"],
                    score["assembly_extent"],
                    order,
                    cols,
                    rectangles,
                    grids,
                )
            )
        if not candidates:
            return None
        best = min(candidates, key=lambda c: c[:4])
        return best[-2], best[-1]

    built = build(roots[0])
    if built is None:
        return None
    rectangles, grids = built
    findings, measured = assess(problem, rectangles, grids)
    if findings:
        raise RuntimeError("Constructive seed failed independent checking")
    return Result(
        ResultStatus.FEASIBLE,
        StrictStatus.SAT,
        rectangles=rectangles,
        grids=grids,
        measurements=measured,
        problem_fingerprint=problem.fingerprint,
        reason="Checked recursive grid seed; no optimum claimed",
    )
