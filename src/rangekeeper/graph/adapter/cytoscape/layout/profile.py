"""Bounded declarative presentation profile over a freshly completed graph.

No project identifiers, source parsing, executable expressions or prior layouts.
"""

from copy import deepcopy
from math import isfinite

from rangekeeper.graph import Assembly as GraphAssembly

from .model import Arrangement, Assembly, Node, Preference, Problem, Weights
from .similarity import Signal, affinities

# Versioned library-owned rendering policy. Project files only bind domain fields.
_STACKED_COMPACT_V1: dict = {
    "canvas": {"width": 16000, "height": 30000},
    "footprints": {"node_width": 248, "node_height": 44, "assembly_min_width": 280},
    "spacing": {"padding": 16, "header": 28, "gap": 12},
    "weights": {
        "grid": 4,
        "direction": 3,
        "order": 6,
        "similarity": 3,
        "compactness": 1,
    },
}
_PRESENTATION_NOTES = (
    "Groups stack vertically with gaps based on drawn rectangle heights; member grids can wrap.",
    "Drag nodes or assembly headers to arrange; boxes fit visible members. Red outlines flag overlaps or incorrect enclosure. Optional amber advisories show insufficient spacing. Changes are session-only; Restore saved layout resets the starting geometry.",
)
_BINDINGS = {"grid_classifications", "stack_order", "signals", "rationales", "notes"}


def resolve(profile: dict) -> dict:
    """Resolve authored bindings into an explicit, captured presentation policy.

    Legacy v1 profiles retain their exact policy and notes. V2 selects a versioned
    RK preset. Returned dictionaries never share mutable defaults with callers.
    """
    if not isinstance(profile, dict):
        raise TypeError("Layout profile must be a mapping")
    schema = profile.get("schema")
    if schema == "rk-layout-profile-v1":
        required = _BINDINGS | {"schema", "canvas", "footprints", "weights"}
        if set(profile) != required:
            raise ValueError("Unknown or missing legacy layout profile fields")
        resolved = deepcopy(profile)
        resolved["spacing"] = {"padding": 16, "header": 28, "gap": 12}
    elif schema == "rk-layout-profile-v2":
        if set(profile) != _BINDINGS | {"schema", "preset"}:
            raise ValueError("Unknown or missing layout profile fields")
        if profile["preset"] != "stacked-compact-v1":
            raise ValueError("Unknown layout preset")
        resolved = deepcopy(_STACKED_COMPACT_V1)
        resolved.update({key: deepcopy(profile[key]) for key in _BINDINGS})
        if not isinstance(resolved["notes"], list) or any(
            not isinstance(n, str) for n in resolved["notes"]
        ):
            raise ValueError("Layout notes must be a list of strings")
        resolved["notes"] = [*_PRESENTATION_NOTES, *resolved["notes"]]
    else:
        raise ValueError("Unsupported layout profile schema")
    resolved["schema"] = "rk-layout-resolved-profile-v1"
    return resolved


def prepare(graph, profile: dict):
    """Build geometry inputs and an inspectable signal report without graph writes."""
    profile = resolve(profile)
    canvas, sizes = profile["canvas"], profile["footprints"]
    if set(canvas) != {"width", "height"} or set(sizes) != {
        "node_width",
        "node_height",
        "assembly_min_width",
    }:
        raise ValueError("Invalid canvas or footprint fields")
    order = profile["stack_order"]
    if (
        set(order) != {"classification", "feature", "descending"}
        or type(order["descending"]) is not bool
    ):
        raise ValueError("Invalid stack ordering selector")
    if not isinstance(profile["grid_classifications"], list) or any(
        not isinstance(v, str) for v in profile["grid_classifications"]
    ):
        raise ValueError("Grid classifications must be a list of codes")
    if set(profile["rationales"]) != {"grid", "stack"}:
        raise ValueError("Grid and stack rationales required")
    signals = tuple(Signal(**s) for s in profile["signals"])
    entities = {str(e.id): e for e in graph.entities}
    groups = [e for e in graph.entities if isinstance(e, GraphAssembly)]
    nodes = tuple(
        Node(
            str(e.id), f"{e.code} | {e.name}", sizes["node_width"], sizes["node_height"]
        )
        for e in graph.entities
        if not isinstance(e, GraphAssembly)
    )
    assemblies = tuple(
        Assembly(
            str(a.id),
            f"{a.code} | {a.name}",
            tuple(sorted(str(i) for i in a.entity_ids)),
            sizes["assembly_min_width"],
        )
        for a in groups
    )
    # Construct and validate membership before walking any descendant ranges.
    base = Problem(
        nodes,
        assemblies,
        **canvas,
        **profile["spacing"],
        weights=Weights(**profile["weights"]),
    )
    preferences, arrangements, report = [], [], {}

    def values(identifier):
        candidates = (
            [entities[i] for i in {identifier, *base.descendants(identifier)}]
            if isinstance(entities[identifier], GraphAssembly)
            else [entities[identifier]]
        )
        selected = [
            e
            for e in candidates
            if e.classification and e.classification.code == order["classification"]
        ]
        found = []
        for e in selected:
            feature = e.features.get(order["feature"])
            fact = graph.provenance.fact_for(feature) if feature is not None else None
            value = feature.value if feature is not None else None
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or (fact is not None and fact.current_claim is None)
            ):
                return []  # Incomplete evidence must not imply a complete range.
            found.append(value)
        return found

    for a in assemblies:
        original = entities[a.id]
        if (
            original.classification
            and original.classification.code in profile["grid_classifications"]
        ):
            edges, explanation = affinities(graph, a.members, signals)
            preferences.append(
                Preference(
                    a.id,
                    "horizontal",
                    affinities=edges,
                    rationale=profile["rationales"]["grid"],
                )
            )
            report[a.id] = {"kind": "grid", "similarity": explanation}
        else:
            ranges = {i: values(i) for i in a.members}
            pairs = tuple(
                (i, j, "y")
                for i, vi in ranges.items()
                for j, vj in ranges.items()
                if i != j
                and vi
                and vj
                and (min(vi) > max(vj) if order["descending"] else max(vi) < min(vj))
            )
            preferences.append(
                Preference(
                    a.id,
                    "vertical",
                    orders=pairs,
                    rationale=profile["rationales"]["stack"],
                )
            )
            arrangements.append(Arrangement(a.id, "column", spacing="packed"))
            report[a.id] = {
                "kind": "stack",
                "ranges": ranges,
                "orders": pairs,
                "missing_ranges": [i for i, v in ranges.items() if not v],
            }
    from dataclasses import replace

    return replace(
        base, preferences=tuple(preferences), arrangements=tuple(arrangements)
    ), report
