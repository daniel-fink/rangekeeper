"""Packed flow parity and successful-bundle publication boundaries."""

import json
import os
from copy import deepcopy
from dataclasses import replace
from importlib.util import find_spec

import pytest

from rangekeeper.graph.adapter.cytoscape import validate_document
from rangekeeper.graph.adapter.cytoscape.layout.check import check, metrics
from rangekeeper.graph.adapter.cytoscape.layout.model import (
    Arrangement,
    Assembly,
    Node,
    Preference,
    Problem,
    Weights,
    from_document,
)
from rangekeeper.graph.adapter.cytoscape.layout.seed import grid_seed
from rangekeeper.graph.adapter.cytoscape.layout.viewer import (
    export_layout_review,
    with_saved_layout,
)


def problem(flow="column"):
    return Problem(
        (Node("a", "A", 60, 30), Node("b", "B", 90, 70), Node("c", "C", 50, 40)),
        (Assembly("g", "G", ("a", "b", "c"), 140),),
        width=500,
        height=500,
        weights=Weights(),
        preferences=(
            Preference(
                "g",
                orders=(
                    ("a", "b", "y" if flow == "column" else "x"),
                    ("b", "c", "y" if flow == "column" else "x"),
                ),
            ),
        ),
        arrangements=(Arrangement("g", flow, spacing="packed"),),
    )


def document(p):
    ids = [o.id for o in (*p.nodes, *p.assemblies)]
    return {
        "name": "Synthetic",
        "elements": [
            {
                "data": {
                    "id": i,
                    "label": i,
                    "kind": "assembly" if i == "g" else "entity",
                }
            }
            for i in ids
        ],
        "assemblies": {
            "g": {"name": "G", "entities": ["a", "b", "c"], "relationships": []}
        },
        "details": {i: {} for i in ids},
        "claims": {},
        "positions": {i: {"x": 0, "y": 0} for i in ids},
        "notes": [],
        "anchors": [],
        "diagnostics": {"ambiguousParents": [], "containmentCycles": []},
    }


@pytest.mark.parametrize("flow", ["row", "column"])
def test_packed_uses_member_sizes_and_preserves_old_serialization(flow):
    p = problem(flow)
    r = grid_seed(p)
    assert r is not None
    assert r is not None
    old = replace(
        p,
        schema_version=3,
        arrangements=(replace(p.arrangements[0], spacing="uniform"),),
    )
    previous = grid_seed(old)
    assert previous is not None
    assert "spacing" not in old.document()["arrangements"][0]
    assert from_document(old.document()).fingerprint == old.fingerprint
    assert from_document(p.document()) == p
    assert not check(p, r.rectangles) and r.measurements["grid_displacement"] == 0
    axis = "height" if flow == "column" else "width"
    assert getattr(r.rectangles["g"], axis) < getattr(previous.rectangles["g"], axis)
    moved = dict(r.rectangles)
    last = moved["c"]
    moved["c"] = replace(
        last, **({"y": last.y + 1} if flow == "column" else {"x": last.x + 1})
    )
    assert any(f.code == "arrangement" for f in check(p, moved))
    repeated = grid_seed(p)
    assert repeated is not None
    assert repeated.geometry_document() == r.geometry_document()


@pytest.mark.skipif(
    find_spec("z3") is None or not os.environ.get("RK_MINIZINC"),
    reason="Requires optional solvers",
)
@pytest.mark.parametrize("flow", ["row", "column"])
def test_native_packed_contract_and_scores(flow):
    from rangekeeper.graph.adapter.cytoscape.layout.minizinc_solver import solve as cp
    from rangekeeper.graph.adapter.cytoscape.layout.z3_solver import solve as z3

    p = problem(flow)
    seed = grid_seed(p)
    assert seed is not None
    for solve in (z3, cp):
        fixed = solve(p, initial=seed, optimize=False, time_limit=5)
        assert fixed.status == "feasible", fixed.reason
        assert (
            fixed.rectangles == seed.rectangles
            and fixed.measurements == seed.measurements
        )
        free = solve(p, optimize=False, time_limit=5)
        assert free.status == "feasible", free.reason
        assert not check(p, free.rectangles)
        assert metrics(p, free.rectangles, free.grids) == free.measurements


def test_saved_snapshot_rejects_stale_and_invalid_results_without_mutation():
    p = problem()
    r = grid_seed(p)
    assert r is not None
    doc = document(p)
    before = deepcopy(doc)
    saved = with_saved_layout(doc, p, r)
    validate_document(saved)
    assert doc == before
    changed = deepcopy(saved)
    changed["details"]["a"]["name"] = "Changed"
    with pytest.raises(ValueError, match="snapshot"):
        validate_document(changed)
    changed = deepcopy(saved)
    changed["savedLayout"]["geometry"]["rectangles"]["a"]["y"] += 1
    with pytest.raises(ValueError, match="fingerprint"):
        validate_document(changed)
    with pytest.raises(ValueError, match="successful"):
        with_saved_layout(doc, p, replace(r, status="unknown"))
    with pytest.raises(ValueError, match="strict"):
        with_saved_layout(doc, p, replace(r, mode="diagnostic"))
    changed = deepcopy(saved)
    changed["positions"]["a"]["x"] += 1
    with pytest.raises(ValueError, match="centres"):
        validate_document(changed)


def test_failed_export_preserves_last_successful_pointer_and_bundle(
    tmp_path, monkeypatch
):
    from rangekeeper.graph.adapter import cytoscape

    p = problem()
    r = grid_seed(p)
    assert r is not None
    doc = document(p)
    path = export_layout_review(doc, p, r, tmp_path)
    pointer = (tmp_path / "latest.json").read_bytes()
    files = {f.name: f.read_bytes() for f in path.iterdir()}

    def fail(*args):
        raise OSError("Simulated interrupted export")

    monkeypatch.setattr(cytoscape, "write_viewer", fail)
    with pytest.raises(OSError, match="interrupted"):
        export_layout_review(doc, p, r, tmp_path)
    assert (tmp_path / "latest.json").read_bytes() == pointer
    assert {f.name: f.read_bytes() for f in path.iterdir()} == files
    assert len(list((tmp_path / "runs").iterdir())) == 1
    assert json.loads(pointer)["run"] == f"runs/{path.name}"
