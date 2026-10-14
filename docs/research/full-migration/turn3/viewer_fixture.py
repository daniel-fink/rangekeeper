"""Export a synthetic gallery for the saved-layout pointer interaction test."""

import argparse
from pathlib import Path

from rangekeeper.adapters.cytoscape import write_viewer
from rangekeeper.adapters.cytoscape.layout.check import check, metrics
from rangekeeper.adapters.cytoscape.layout.model import (
    Arrangement,
    Assembly,
    Node,
    Problem,
    Rect,
    Weights,
)
from rangekeeper.adapters.cytoscape.layout.result import Result
from rangekeeper.adapters.cytoscape.layout.seed import grid_seed
from rangekeeper.adapters.cytoscape.layout.viewer import with_saved_layout


def document(problem, name):
    objects = (*problem.nodes, *problem.assemblies)
    groups = {
        a.id: {"name": a.label, "entities": list(a.members), "relationships": []}
        for a in problem.assemblies
    }
    return {
        "name": name,
        "elements": [
            {
                "data": {
                    "id": o.id,
                    "label": o.label,
                    "kind": "assembly" if o.id in groups else "entity",
                }
            }
            for o in objects
        ],
        "assemblies": groups,
        "details": {
            o.id: {"name": o.label, "measurements": [], "labels": [], "features": []}
            for o in objects
        },
        "claims": {},
        "positions": {o.id: {"x": 0, "y": 0} for o in objects},
        "notes": ["Synthetic interaction fixture."],
        "anchors": [],
        "diagnostics": {"ambiguousParents": [], "containmentCycles": []},
    }


def gallery():
    tree = Problem(
        tuple(Node(i, f"Item {i.upper()}", 248, 44) for i in "abcdef"),
        (
            Assembly("shelf-a", "Shelf A", tuple("abc"), 280),
            Assembly("shelf-b", "Shelf B", tuple("def"), 280),
            Assembly("root", "Storage", ("shelf-a", "shelf-b"), 280),
        ),
        weights=Weights(),
        width=1600,
        height=2000,
        arrangements=(Arrangement("root", "column", spacing="packed"),),
    )
    seed = grid_seed(tree)
    assert seed is not None
    saved = with_saved_layout(document(tree, "Nested shelves"), tree, seed)
    shared = Problem(
        tuple(
            Node(i, label, 120, 44)
            for i, label in (("a", "A only"), ("s", "Shared"), ("z", "B only"))
        ),
        (
            Assembly("A", "Assembly A", ("a", "s"), 140),
            Assembly("B", "Assembly B", ("s", "z"), 140),
        ),
        width=600,
        height=400,
    )
    rectangles = {
        "a": Rect(32, 100, 120, 44),
        "s": Rect(180, 100, 120, 44),
        "z": Rect(328, 100, 120, 44),
        "A": Rect(16, 44, 300, 116),
        "B": Rect(164, 0, 300, 160),
    }
    assert not check(shared, rectangles), check(shared, rectangles)
    grids = {
        "A": {"x": 32, "y": 100, "columns": 2},
        "B": {"x": 180, "y": 100, "columns": 2},
    }
    result = Result(
        "feasible",
        "feasible",
        rectangles=rectangles,
        grids=grids,
        measurements=metrics(shared, rectangles, grids),
        problem_fingerprint=shared.fingerprint,
    )
    return [
        saved,
        document(tree, "Legacy shelves"),
        with_saved_layout(document(shared, "Shared objects"), shared, result),
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    write_viewer(gallery(), args.output / "index.html")
