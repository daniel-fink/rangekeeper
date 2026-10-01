"""Independent arithmetic checker. No Z3 import or solver predicates."""

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations

from .model import Problem, Rect, grid_templates


@dataclass(frozen=True)
class Finding:
    code: str
    objects: tuple[str, ...]
    message: str


def separated(a: Rect, b: Rect, gap: int = 0) -> bool:
    return (
        a.right + gap <= b.x
        or b.right + gap <= a.x
        or a.bottom + gap <= b.y
        or b.bottom + gap <= a.y
    )


def check(problem: Problem, rectangles: Mapping[str, Rect]) -> tuple[Finding, ...]:
    findings: list[Finding] = []

    def add(code, ids, text):
        findings.append(Finding(code, tuple(ids), text))

    expected = {o.id for o in (*problem.nodes, *problem.assemblies)}
    for i in sorted(expected - rectangles.keys()):
        add("missing", [i], "Missing object rectangle")
    for i in sorted(rectangles.keys() - expected):
        add("unexpected", [i], "Unexpected object rectangle")
    for i, r in rectangles.items():
        if (
            not isinstance(r, Rect)
            or any(type(v) is not int for v in (r.x, r.y, r.width, r.height))
            or r.width <= 0
            or r.height <= 0
        ):
            add("geometry", [i], "Invalid integer rectangle")
    if findings:
        return tuple(findings)
    for i, r in rectangles.items():
        if r.x < 0 or r.y < 0 or r.right > problem.width or r.bottom > problem.height:
            add("bounds", [i], "Outside the stated canvas bounds")
    for i, x, y in problem.pins:
        if (rectangles[i].x, rectangles[i].y) != (x, y):
            add("pin", [i], "Pinned position changed")
    for n in problem.nodes:
        r = rectangles[n.id]
        if (r.width, r.height) != (n.width, n.height):
            add("size", [n.id], "Node footprint changed")
    for a in problem.assemblies:
        r = rectangles[a.id]
        if r.width < a.min_width or r.height < problem.header + 2 * problem.padding:
            add("size", [a.id], "Assembly is smaller than its header/content minimum")
        for i in a.members:
            c = rectangles[i]
            if not (
                r.x + problem.padding <= c.x
                and c.right <= r.right - problem.padding
                and r.y + problem.header + problem.padding <= c.y
                and c.bottom <= r.bottom - problem.padding
            ):
                add("containment", [i, a.id], "Member footprint outside content region")
        descendants = problem.descendants(a.id)
        for n in problem.nodes:
            if n.id not in descendants and not separated(
                rectangles[n.id], r, problem.gap
            ):
                add(
                    "exclusion",
                    [n.id, a.id],
                    "Nonmember intersects assembly clearance region",
                )
    groups = {a.id: a for a in problem.assemblies}
    for setting in problem.arrangements:
        if setting.flow == "grid":
            continue
        parent = rectangles[setting.assembly]
        vertical = setting.flow == "column"
        members = groups[setting.assembly].members
        start = (
            parent.x + problem.padding
            if vertical
            else parent.y + problem.header + problem.padding
        )
        span = (
            parent.width - 2 * problem.padding
            if vertical
            else parent.height - problem.header - 2 * problem.padding
        )
        for i in members:
            child = rectangles[i]
            size = child.width if vertical else child.height
            offset = {"start": 0, "center": (span - size) // 2, "end": span - size}[
                setting.alignment
            ]
            if (child.x if vertical else child.y) != start + offset:
                add(
                    "arrangement",
                    [setting.assembly, i],
                    "Member violates cross-axis alignment",
                )
        if setting.spacing == "packed" and members:
            ordered = sorted(
                (rectangles[i] for i in members), key=lambda r: r.y if vertical else r.x
            )
            expected = (
                parent.y + problem.header + problem.padding
                if vertical
                else parent.x + problem.padding
            )
            for child in ordered:
                if (child.y if vertical else child.x) != expected:
                    add(
                        "arrangement",
                        [setting.assembly],
                        "Packed flow has an incorrect gap or origin",
                    )
                expected = (child.bottom if vertical else child.right) + problem.gap
        for i, j in combinations(members, 2):
            a, b = rectangles[i], rectangles[j]
            separated_flow = (
                (a.bottom + problem.gap <= b.y or b.bottom + problem.gap <= a.y)
                if vertical
                else (a.right + problem.gap <= b.x or b.right + problem.gap <= a.x)
            )
            if not separated_flow:
                add(
                    "arrangement",
                    [setting.assembly, i, j],
                    "Unwrapped members overlap on flow axis",
                )
    # Partial overlap can express shared membership. Full enclosure of an
    # unrelated assembly would incorrectly suggest assembly membership.
    for outer in problem.assemblies:
        descendants = problem.descendants(outer.id)
        r = rectangles[outer.id]
        for inner in problem.assemblies:
            if inner.id == outer.id or inner.id in descendants:
                continue
            c = rectangles[inner.id]
            if (
                r.x <= c.x
                and r.y <= c.y
                and c.right <= r.right
                and c.bottom <= r.bottom
            ):
                add(
                    "exclusion",
                    [inner.id, outer.id],
                    "Unrelated assembly fully enclosed",
                )
    # Group frames may overlap. Their full-width header strips are solid obstacles.
    obstacles = {n.id: rectangles[n.id] for n in problem.nodes}
    obstacles.update({
        a.id: Rect(
            rectangles[a.id].x,
            rectangles[a.id].y,
            rectangles[a.id].width,
            problem.header,
        )
        for a in problem.assemblies
    })
    for i, j in combinations(sorted(obstacles), 2):
        if not separated(obstacles[i], obstacles[j], problem.gap):
            add(
                "collision", [i, j], "Node/label or header footprints overlap clearance"
            )
    return tuple(findings)


def metrics(
    problem: Problem, rectangles: Mapping[str, Rect], grids: Mapping[str, dict]
):
    """Arithmetic reproduction of the objective vector and explicit grid witnesses."""
    displacement = 0
    grid_score = 0
    for a in problem.assemblies:
        templates = grid_templates(problem, a)
        if not templates:
            continue
        witness = grids[a.id]
        if any(type(witness[k]) is not int for k in ("x", "y", "columns")):
            raise ValueError("Grid witnesses require integers")
        if not 1 <= witness["columns"] <= len(templates):
            raise ValueError("Invalid grid column count")
        r = rectangles[a.id]
        gx, gy = witness["x"], witness["y"]
        if not (
            r.x + problem.padding <= gx <= r.right - problem.padding
            and r.y + problem.header + problem.padding
            <= gy
            <= r.bottom - problem.padding
        ):
            raise ValueError("Grid origin outside assembly content")
        pitch_x = max(rectangles[i].width for i in a.members) + problem.gap
        pitch_y = max(rectangles[i].height for i in a.members) + problem.gap
        slots = witness.get("slots")
        if problem.weights is not None:
            if (
                not isinstance(slots, dict)
                or set(slots) != set(a.members)
                or any(type(v) is not int for v in slots.values())
                or sorted(slots.values()) != list(range(len(a.members)))
            ):
                raise ValueError("Grid slots must be a complete member permutation")
            template = [
                (i, slots[i] % witness["columns"], slots[i] // witness["columns"])
                for i in a.members
            ]
        else:
            template = templates[witness["columns"] - 1]
        setting = next((v for v in problem.arrangements if v.assembly == a.id), None)
        if setting and setting.flow != "grid":
            assert isinstance(slots, dict)  # Arrangements require weighted grids.
            expected_columns = 1 if setting.flow == "column" else len(a.members)
            if witness["columns"] != expected_columns:
                raise ValueError("Grid columns violate unwrapped arrangement")
            for i, j in combinations(a.members, 2):
                before, after = (i, j) if slots[i] < slots[j] else (j, i)
                first, second = rectangles[before], rectangles[after]
                if (
                    first.bottom + problem.gap > second.y
                    if setting.flow == "column"
                    else first.right + problem.gap > second.x
                ):
                    raise ValueError("Grid slots contradict unwrapped flow order")
        local = 0
        for i, col, row in template:
            dx, dy = col * pitch_x, row * pitch_y
            if setting and setting.spacing == "packed":
                assert isinstance(slots, dict)
                previous = [j for j in a.members if slots[j] < slots[i]]
                if setting.flow == "column":
                    dy = sum(rectangles[j].height + problem.gap for j in previous)
                else:
                    dx = sum(rectangles[j].width + problem.gap for j in previous)
            n = rectangles[i]
            local += abs(n.x - gx - dx) + abs(n.y - gy - dy)
        displacement += local
        strength = next(
            (p.strength for p in problem.preferences if p.assembly == a.id), 1
        )
        grid_score += strength * (local // len(a.members))
    width = max(r.right for r in rectangles.values())
    height = max(r.bottom for r in rectangles.values())
    # Origin is fixed at the canvas top-left. Including unused leading margin in
    # extent breaks translation symmetry without selecting an arbitrary node.
    result = {
        "false_enclosures": sum(
            f.code == "exclusion" for f in check(problem, rectangles)
        ),
        "grid_displacement": displacement,
        "extent": width + height,
        "width": width,
        "height": height,
        "assembly_extent": sum(
            rectangles[a.id].width + rectangles[a.id].height for a in problem.assemblies
        ),
    }
    if problem.weights is not None:
        direction = order = similarity = 0
        details = {}
        groups = {a.id: a for a in problem.assemblies}
        for p in problem.preferences:
            members = groups[p.assembly].members
            d = o = s = 0
            if len(members) > 1:
                w = grids[p.assembly]["columns"]
                h = (len(members) + w - 1) // w
                d = {
                    "unspecified": 0,
                    "horizontal": max(0, 2 * h - w),
                    "vertical": max(0, 2 * w - h),
                    "balanced": abs(w - h),
                }[p.direction] * problem.style_unit
            for before, after, axis in p.orders:
                a, b = rectangles[before], rectangles[after]
                ca, cb = (
                    (2 * a.x + a.width, 2 * b.x + b.width)
                    if axis == "x"
                    else (2 * a.y + a.height, 2 * b.y + b.height)
                )
                o += max(0, ca + 2 - cb)
            denominator = 2 * len(p.orders)
            o = (
                (o + (denominator - 1 if problem.schema_version >= 3 else 0))
                // denominator
                if p.orders
                else 0
            )
            for left, right, weight in p.affinities:
                a, b = rectangles[left], rectangles[right]
                s += weight * (
                    max(0, a.x - b.right, b.x - a.right)
                    + max(0, a.y - b.bottom, b.y - a.bottom)
                )
            s = s // sum(t[2] for t in p.affinities) if p.affinities else 0
            details[p.assembly] = {
                "direction": d,
                "order": o,
                "similarity": s,
                "strength": p.strength,
            }
            direction += p.strength * d
            order += p.strength * o
            similarity += p.strength * s
        weights = problem.weights
        result.update(
            grid_score=grid_score,
            direction_score=direction,
            order_score=order,
            similarity_score=similarity,
            preference_details=details,
        )
        result["style_cost"] = (
            weights.grid * grid_score
            + weights.direction * direction
            + weights.order * order
            + weights.similarity * similarity
            + weights.compactness * result["extent"]
        )
    return result
