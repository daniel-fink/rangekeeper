"""Bounded declarative presentation profile over a freshly completed graph.

No project identifiers, source parsing, executable expressions or prior layouts.
"""

from rangekeeper.adapters.cytoscape.layout.model import (
    ArrangementFlow,
    ArrangementSpacing,
    PreferenceDirection,
)
from copy import deepcopy
from math import isfinite

from collections.abc import Mapping
from uuid import UUID
from rangekeeper.model import Model, Assembly as ModelAssembly
from rangekeeper.model.definitions import classification

from .model import Axis, Arrangement, Assembly, Node, Preference, Problem, Weights
from .similarity import Signal, affinities, select

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


def resolve(profile: Mapping[str, object]) -> dict:
    """Resolve a v3 profile to detached policy data; old versions require upgrade.

    UUID classification selectors and Value keys are explicit. An upgraded v1
    profile can retain its custom geometry policy without changing the preset.
    """
    if not isinstance(profile, Mapping):
        raise TypeError("Layout profile must be a mapping")
    if profile.get("schema") != "rk-layout-profile-v3":
        raise ValueError(
            "Unsupported layout profile; use migration.layout.upgrade_profile"
        )
    if set(profile) - (
        _BINDINGS | {"schema", "preset", "policy"}
    ) or not _BINDINGS <= set(profile):
        raise ValueError("Unknown or missing layout profile fields")
    if profile.get("preset") != "stacked-compact-v1":
        raise ValueError("Unknown layout preset")
    resolved = deepcopy(_STACKED_COMPACT_V1)
    if "policy" in profile:
        policy = profile["policy"]
        if not isinstance(policy, Mapping) or set(policy) != set(resolved):
            raise ValueError("Invalid explicit geometry policy")
        resolved = deepcopy(dict(policy))
    resolved.update({key: deepcopy(profile[key]) for key in _BINDINGS})
    if not isinstance(resolved["notes"], list) or any(
        not isinstance(n, str) for n in resolved["notes"]
    ):
        raise ValueError("Layout notes must be a list of strings")
    resolved["notes"] = [*_PRESENTATION_NOTES, *resolved["notes"]]
    resolved["schema"] = "rk-layout-resolved-profile-v2"
    return resolved


def prepare(model: Model, profile: Mapping[str, object]):
    """Build geometry inputs and an inspectable signal report without Model writes."""
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
        set(order) - {"classification", "source", "key", "units", "descending"}
        or not {"classification", "source", "key", "descending"} <= set(order)
        or type(order["descending"]) is not bool
    ):
        raise ValueError("Invalid stack ordering selector")
    if not isinstance(profile["grid_classifications"], list) or any(
        not isinstance(v, str) for v in profile["grid_classifications"]
    ):
        raise ValueError("Grid classifications must be a list of UUID strings")
    if set(profile["rationales"]) != {"grid", "stack"}:
        raise ValueError("Grid and stack rationales required")
    if order["source"] not in {"property", "quantity"} or (
        order["source"] == "quantity" and not order.get("units")
    ):
        raise ValueError("Invalid ordering Value selector or missing units")
    # Resolve every UUID in the pinned revision, even for empty selections.
    grid_ids = {UUID(uid) for uid in profile["grid_classifications"]}
    order_id = UUID(order["classification"])
    for uid in {*grid_ids, order_id}:
        classification(model.definitions, uid)
    signals = tuple(Signal(**s) for s in profile["signals"])
    entities = {str(e.id): e for e in model.find_entities()}
    groups = [e for e in model.find_entities() if isinstance(e, ModelAssembly)]
    nodes = tuple(
        Node(
            str(e.id), f"{e.code} | {e.name}", sizes["node_width"], sizes["node_height"]
        )
        for e in model.find_entities()
        if not isinstance(e, ModelAssembly)
    )
    assemblies = tuple(
        Assembly(
            str(a.id),
            f"{a.code} | {a.name}",
            tuple(sorted(str(i) for i in (a.entities or ()))),
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
            if isinstance(entities[identifier], ModelAssembly)
            else [entities[identifier]]
        )
        selected = [
            e for e in candidates if e.classification and e.classification == order_id
        ]
        found = []
        for e in selected:
            value = select(
                model, e, order["source"], order["key"], units=order.get("units")
            )
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                return []  # Incomplete evidence must not imply a complete range.
            found.append(value)
        return found

    for a in assemblies:
        original = entities[a.id]
        if original.classification and original.classification in grid_ids:
            edges, explanation = affinities(model, a.members, signals)
            preferences.append(
                Preference(
                    a.id,
                    PreferenceDirection.HORIZONTAL,
                    affinities=edges,
                    rationale=profile["rationales"]["grid"],
                )
            )
            report[a.id] = {"kind": "grid", "similarity": explanation}
        else:
            ranges = {i: values(i) for i in a.members}
            pairs = tuple(
                (i, j, Axis.Y)
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
                    PreferenceDirection.VERTICAL,
                    orders=pairs,
                    rationale=profile["rationales"]["stack"],
                )
            )
            arrangements.append(
                Arrangement(
                    a.id, ArrangementFlow.COLUMN, spacing=ArrangementSpacing.PACKED
                )
            )
            report[a.id] = {
                "kind": "stack",
                "ranges": ranges,
                "orders": tuple((a, b, axis.value) for a, b, axis in pairs),
                "missing_ranges": [i for i, v in ranges.items() if not v],
            }
    from dataclasses import replace

    return (
        replace(base, preferences=tuple(preferences), arrangements=tuple(arrangements)),
        report,
    )
