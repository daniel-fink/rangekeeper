"""Solver-independent, integer-pixel geometry for the layout research prototype."""

import json
from dataclasses import asdict, dataclass
from hashlib import sha256


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    width: int = 96
    height: int = 40


@dataclass(frozen=True)
class Assembly:
    id: str
    label: str
    members: tuple[str, ...]
    min_width: int = 140


@dataclass(frozen=True)
class Preference:
    """Soft intent only; pairs reference direct members, never new memberships."""

    assembly: str
    direction: str = "unspecified"
    # (before, after, axis); partial orders and even conflicting wishes are soft.
    orders: tuple[tuple[str, str, str], ...] = ()
    # Positive affinity, 1..100. Missing evidence produces no edge.
    affinities: tuple[tuple[str, str, int], ...] = ()
    strength: int = 1
    rationale: str = ""


@dataclass(frozen=True)
class Arrangement:
    """Explicit presentation constraints, separate from soft semantic preferences.

    Grid permits wrapping. Row and column prohibit wrapping and align direct
    member rectangles within the parent's content region on the cross axis.
    """

    assembly: str
    flow: str = "grid"
    alignment: str = "start"
    spacing: str = "uniform"


@dataclass(frozen=True)
class Weights:
    """Experimental weights, not accepted product defaults. Scores use pixel proxies."""

    grid: int = 4
    direction: int = 3
    order: int = 6
    similarity: int = 3
    compactness: int = 1


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height


@dataclass(frozen=True)
class Problem:
    nodes: tuple[Node, ...]
    assemblies: tuple[Assembly, ...]
    width: int = 1200
    height: int = 900
    padding: int = 16
    header: int = 28
    gap: int = 12
    pins: tuple[tuple[str, int, int], ...] = ()
    # None keeps the original stable-order, lexicographic prototype unchanged.
    weights: Weights | None = None
    preferences: tuple[Preference, ...] = ()
    style_unit: int = 40
    arrangements: tuple[Arrangement, ...] = ()
    schema_version: int = 4

    def __post_init__(self):
        if self.schema_version not in (2, 3, 4):
            raise ValueError("Unsupported layout problem version")
        if self.arrangements and (self.schema_version < 3 or self.weights is None):
            raise ValueError("Arrangements require v3 and explicit weights")
        ids = [n.id for n in (*self.nodes, *self.assemblies)]
        if not ids or any(not isinstance(i, str) or not i for i in ids):
            raise ValueError("Nonempty string identifiers required")
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate identifiers")
        positive = [self.width, self.height, self.header, self.style_unit]
        positive += [v for n in self.nodes for v in (n.width, n.height)]
        positive += [a.min_width for a in self.assemblies]
        if any(type(v) is not int or v <= 0 for v in positive):
            raise ValueError("Dimensions must be positive integer pixels")
        if any(type(v) is not int or v < 0 for v in (self.padding, self.gap)):
            raise ValueError("Spacing must be nonnegative integer pixels")
        for a in self.assemblies:
            if len(set(a.members)) != len(a.members) or not set(a.members) <= set(ids):
                raise ValueError("Unknown or repeated member")
        active, visited = set(), set()
        groups = {a.id: a for a in self.assemblies}

        def visit(i):
            if i in active:
                raise ValueError("Assembly membership cycle")
            if i in visited or i not in groups:
                return
            active.add(i)
            for child in groups[i].members:
                visit(child)
            active.remove(i)
            visited.add(i)

        for i in groups:
            visit(i)
        if len({i for i, _, _ in self.pins}) != len(self.pins):
            raise ValueError("Repeated pin")
        for i, x, y in self.pins:
            if i not in ids or type(x) is not int or type(y) is not int:
                raise ValueError("Pins require known IDs and integer coordinates")
        if self.preferences and self.weights is None:
            raise ValueError("Preferences require explicit scoring weights")
        if self.weights is not None:
            values = asdict(self.weights).values()
            if any(type(v) is not int or v < 0 for v in values) or not any(values):
                raise ValueError(
                    "Weights must be nonnegative integers, at least one positive"
                )
        if len({p.assembly for p in self.preferences}) != len(self.preferences):
            raise ValueError("Repeated assembly preference")
        if len({a.assembly for a in self.arrangements}) != len(self.arrangements):
            raise ValueError("Repeated arrangement")
        for a in self.arrangements:
            if a.spacing not in {"uniform", "packed"}:
                raise ValueError("Unknown arrangement spacing")
            if a.spacing == "packed" and (self.schema_version < 4 or a.flow == "grid"):
                raise ValueError("Packed spacing requires v4 unwrapped flow")
            if a.assembly not in groups or a.flow not in {"grid", "row", "column"}:
                raise ValueError("Unknown arrangement assembly or flow")
            if a.alignment not in {"start", "center", "end"}:
                raise ValueError("Unknown alignment")
            if a.flow == "grid" and a.alignment != "start":
                raise ValueError("Wrapping grid supports start alignment only")
        for p in self.preferences:
            if p.assembly not in groups or p.direction not in {
                "unspecified",
                "horizontal",
                "vertical",
                "balanced",
            }:
                raise ValueError("Unknown assembly or direction")
            if type(p.strength) is not int or p.strength <= 0:
                raise ValueError("Preference strength must be a positive integer")
            members = set(groups[p.assembly].members)
            pairs = set()
            for a, b, axis in p.orders:
                if a == b or not {a, b} <= members or axis not in {"x", "y"}:
                    raise ValueError(
                        "Order must name distinct direct members and x/y axis"
                    )
            for a, b, weight in p.affinities:
                pair = frozenset((a, b))
                if a == b or not pair <= members or pair in pairs:
                    raise ValueError("Affinity must be a unique pair of direct members")
                if type(weight) is not int or not 1 <= weight <= 100:
                    raise ValueError("Affinity must be an integer from 1 to 100")
                pairs.add(pair)

    def descendants(self, identifier: str) -> frozenset[str]:
        groups = {a.id: a for a in self.assemblies}
        found: set[str] = set()

        def visit(i):
            for child in groups[i].members:
                found.add(child)
                if child in groups:
                    visit(child)

        visit(identifier)
        return frozenset(found)

    def document(self):
        data = asdict(self)
        data.pop("schema_version")
        if self.schema_version == 2:
            data.pop("arrangements")
        elif self.schema_version == 3:
            for arrangement in data["arrangements"]:
                arrangement.pop("spacing")
        return {"schema": f"rk-layout-problem-v{self.schema_version}", **data}

    @property
    def fingerprint(self):
        return sha256(json.dumps(self.document(), sort_keys=True).encode()).hexdigest()


def grid_templates(problem: Problem, assembly: Assembly):
    """Column/row slots for every column count in stable ID order.

    All direct members participate, including child assemblies. Cell pitch uses
    the largest solved member footprint plus the common gap; it is not a hard
    assignment. Shared objects still have only one coordinate pair.
    """
    ids = sorted(assembly.members)
    return tuple(
        tuple((identifier, i % cols, i // cols) for i, identifier in enumerate(ids))
        for cols in range(1, len(ids) + 1)
    )


def from_document(document: dict) -> Problem:
    """Read versioned inputs; historical v2 retains its scoring and fingerprint."""
    data = dict(document)
    schema = data.pop("schema", None)
    if schema not in {
        "rk-layout-problem-v2",
        "rk-layout-problem-v3",
        "rk-layout-problem-v4",
    }:
        raise ValueError("Unsupported layout problem schema")
    if "schema_version" in data or (schema.endswith("v2") and "arrangements" in data):
        raise ValueError("Fields not supported by this schema")
    data["schema_version"] = int(schema[-1])
    if data["schema_version"] < 4 and any(
        "spacing" in a for a in data.get("arrangements", ())
    ):
        raise ValueError("Spacing requires v4 schema")
    data["arrangements"] = tuple(Arrangement(**a) for a in data.get("arrangements", ()))
    data["nodes"] = tuple(Node(**n) for n in data["nodes"])
    assemblies = []
    for a in data["assemblies"]:
        fields = dict(a)
        fields["members"] = tuple(a["members"])
        assemblies.append(Assembly(**fields))
    data["assemblies"] = tuple(assemblies)
    data["weights"] = (
        Weights(**data["weights"]) if data.get("weights") is not None else None
    )
    preferences = []
    for p in data.get("preferences", ()):
        fields = dict(p)
        fields["orders"] = tuple(tuple(o) for o in p.get("orders", ()))
        fields["affinities"] = tuple(tuple(a) for a in p.get("affinities", ()))
        preferences.append(Preference(**fields))
    data["preferences"] = tuple(preferences)
    data["pins"] = tuple(tuple(p) for p in data.get("pins", ()))
    return Problem(**data)
