"""Translate a layout Problem into the data contract of layout.mzn.

This module has no process or filesystem effects; solver orchestration supplies
an optional independently checked incumbent.
"""

from rangekeeper.adapters.cytoscape.layout.model import ArrangementSpacing, Axis
from dataclasses import asdict
from rangekeeper.adapters.cytoscape.layout.reduction import _collision_pairs


def encode(p, initial):
    """Encode stable one-based object indexes and explicit initial geometry."""
    nodes = sorted(p.nodes, key=lambda n: n.id)
    groups = sorted(p.assemblies, key=lambda a: a.id)
    objects = [*nodes, *groups]
    ids = {o.id: i for i, o in enumerate(objects, 1)}
    prefs = {v.assembly: v for v in p.preferences}
    arrangements = {v.assembly: v for v in p.arrangements}
    descendants = p.descendant_index()
    pairs = _collision_pairs(p, descendants)
    membership = [
        (g, ids[i], rank)
        for g, a in enumerate(groups, 1)
        for rank, i in enumerate(sorted(a.members))
    ]
    exclusions = [
        (ids[n.id], ids[a.id])
        for a in groups
        for n in nodes
        if n.id not in descendants[a.id]
    ]
    enclosures = [
        (ids[b.id], ids[a.id])
        for a in groups
        for b in groups
        if b.id != a.id and b.id not in descendants[a.id]
    ]
    orders = [
        (g, ids[b], ids[e], 0 if axis == Axis.X else 1)
        for g, a in enumerate(groups, 1)
        if a.id in prefs
        for b, e, axis in prefs[a.id].orders
    ]
    affinities = [
        (g, ids[l], ids[r], weight)
        for g, a in enumerate(groups, 1)
        if a.id in prefs
        for l, r, weight in prefs[a.id].affinities
    ]
    data = {
        "ceil_order": p.schema_version >= 3,
        "packed": [
            a.id in arrangements
            and arrangements[a.id].spacing == ArrangementSpacing.PACKED
            for a in groups
        ],
        "flow": [
            (
                ("grid", "row", "column").index(arrangements[a.id].flow.value)
                if a.id in arrangements
                else 0
            )
            for a in groups
        ],
        "alignment": [
            (
                ("start", "center", "end").index(arrangements[a.id].alignment.value)
                if a.id in arrangements
                else 0
            )
            for a in groups
        ],
        "neighborhood": False,
        "free_object": [True] * len(objects),
        "free_grid": [True] * len(groups),
        "nc": len(pairs),
        "ci": [ids[i] for i, j in pairs],
        "cj": [ids[j] for i, j in pairs],
        "hinted": initial is not None,
        "nn": len(nodes),
        "ng": len(groups),
        "nm": len(membership),
        "canvas_w": p.width,
        "canvas_h": p.height,
        "padding": p.padding,
        "header": p.header,
        "gap": p.gap,
        "minimum_w": [n.width for n in nodes] + [a.min_width for a in groups],
        "node_h": [n.height for n in nodes],
        "mg": [t[0] for t in membership],
        "mo": [t[1] for t in membership],
        "rank": [t[2] for t in membership],
        "count": [len(a.members) for a in groups],
        "ne": len(exclusions),
        "en": [t[0] for t in exclusions],
        "eg": [t[1] for t in exclusions],
        "na": len(enclosures),
        "ai": [t[0] for t in enclosures],
        "ao": [t[1] for t in enclosures],
        "np": len(p.pins),
        "pi": [ids[i] for i, x, y in p.pins],
        "px": [x for i, x, y in p.pins],
        "py": [y for i, x, y in p.pins],
        "flexible": p.weights is not None,
        "strict": True,
        "fixed": initial is not None,
        "direction": [
            (
                ("unspecified", "horizontal", "vertical", "balanced").index(
                    prefs[a.id].direction.value
                )
                if a.id in prefs
                else 0
            )
            for a in groups
        ],
        "strength": [prefs[a.id].strength if a.id in prefs else 1 for a in groups],
        "style_unit": p.style_unit,
        "weights": list(asdict(p.weights).values()) if p.weights else [0] * 5,
        "no": len(orders),
        "og": [t[0] for t in orders],
        "ob": [t[1] for t in orders],
        "oe": [t[2] for t in orders],
        "axis": [t[3] for t in orders],
        "nf": len(affinities),
        "fg": [t[0] for t in affinities],
        "fl": [t[1] for t in affinities],
        "fr": [t[2] for t in affinities],
        "fw": [t[3] for t in affinities],
        "phase": 0,
        "proved": [-1] * 9,
        "incumbent_bound": 0,
    }
    for key, attr in (("sx", "x"), ("sy", "y"), ("sw", "width"), ("sh", "height")):
        data[key] = [
            getattr(initial.rectangles[o.id], attr) if initial else 0 for o in objects
        ]
    for key, attr, default in (("sgx", "x", 0), ("sgy", "y", 0), ("sc", "columns", 1)):
        data[key] = [
            initial.grids[a.id][attr] if initial and a.members else default
            for a in groups
        ]
    data["ss"] = [
        (
            initial.grids[groups[g - 1].id]["slots"][objects[i - 1].id]
            if initial and p.weights
            else rank
        )
        for g, i, rank in membership
    ]
    return data, objects, groups
