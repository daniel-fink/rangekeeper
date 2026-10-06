"""Explicit unwrapped geometry, score visibility and historical input compatibility."""

import json
from dataclasses import replace
from hashlib import sha256

import pytest

from rangekeeper.adapters.cytoscape.layout.check import check, metrics
from rangekeeper.adapters.cytoscape.layout.model import (
    Arrangement,
    Assembly,
    Node,
    Preference,
    Problem,
    Weights,
    from_document,
)
from rangekeeper.adapters.cytoscape.layout.seed import grid_seed


def fixture(flow, alignment="start"):
    return Problem(
        (Node("a", "A", 31, 21), Node("b", "B", 50, 32), Node("c", "C", 20, 16)),
        (Assembly("g", "G", ("a", "b", "c"), 140),),
        width=500,
        height=500,
        weights=Weights(),
        preferences=(
            Preference(
                "g",
                orders=(
                    ("c", "b", "y" if flow == "column" else "x"),
                    ("b", "a", "y" if flow == "column" else "x"),
                ),
            ),
        ),
        arrangements=(Arrangement("g", flow, alignment),),
    )


@pytest.mark.parametrize("flow", ["row", "column"])
@pytest.mark.parametrize("alignment", ["start", "center", "end"])
def test_seed_enforces_flow_and_cross_alignment(flow, alignment):
    p = fixture(flow, alignment)
    seed = grid_seed(p)
    assert seed is not None and not check(p, seed.rectangles)
    assert seed.grids["g"]["columns"] == (1 if flow == "column" else 3)
    assert seed.measurements["order_score"] == 0
    moved = dict(seed.rectangles)
    r = moved["a"]
    moved["a"] = replace(r, **({"x": r.x + 1} if flow == "column" else {"y": r.y + 1}))
    assert any(f.code == "arrangement" for f in check(p, moved))
    assert from_document(p.document()) == p


def test_no_wrap_does_not_silently_fall_back_to_grid():
    p = replace(fixture("row"), width=150)
    assert grid_seed(p) is None
    assert grid_seed(replace(p, arrangements=())) is not None


def test_old_documents_retain_fingerprint_and_order_rounding():
    p = fixture("row")
    old = replace(p, arrangements=(), preferences=(), schema_version=2)
    document = json.loads(json.dumps(old.document()))
    assert "arrangements" not in document and "schema_version" not in document
    restored = from_document(document)
    assert (
        restored.fingerprint
        == sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()
    )
    seed = grid_seed(old)
    assert seed is not None
    # A tied-height pair diluted by a satisfied pair used to round to zero.
    old = replace(
        old,
        preferences=(Preference("g", orders=(("a", "b", "y"), ("b", "c", "x"))),),
    )
    # Build an explicit single row with all centres tied on y; differing x ensures
    # a fulfilled x order dilutes the one-pixel vertical deficit.
    from rangekeeper.adapters.cytoscape.layout.model import Rect

    rects = {
        "g": Rect(0, 0, 200, 100),
        "a": Rect(16, 44, 31, 20),
        "b": Rect(59, 44, 50, 20),
        "c": Rect(121, 44, 20, 20),
    }
    grids = {"g": {"x": 16, "y": 44, "columns": 3, "slots": {"a": 0, "b": 1, "c": 2}}}
    # metrics independently scores rectangles; size validation is a separate check.
    assert metrics(old, rects, grids)["order_score"] == 0
    assert metrics(replace(old, schema_version=3), rects, grids)["order_score"] == 1


@pytest.mark.minizinc
@pytest.mark.z3
@pytest.mark.parametrize(
    "flow,alignment", [("column", "start"), ("row", "center"), ("column", "end")]
)
def test_both_native_engines_obey_arrangements_and_new_scores(flow, alignment):
    from rangekeeper.adapters.cytoscape.layout.minizinc_solver import solve as cp
    from rangekeeper.adapters.cytoscape.layout.z3_solver import solve as z3

    p = fixture(flow, alignment)
    seed = grid_seed(p)
    assert seed is not None
    for solve in (z3, cp):
        fixed = solve(p, initial=seed, optimize=False, time_limit=5)
        assert fixed.status == "feasible", fixed.reason
        assert (
            fixed.rectangles == seed.rectangles
            and fixed.measurements == seed.measurements
        )
        native = solve(p, optimize=False, time_limit=5)
        assert native.status == "feasible", native.reason
        assert not check(p, native.rectangles)
        assert native.measurements == metrics(p, native.rectangles, native.grids)


def test_invalid_arrangement_profile_rejected():
    p = fixture("column")
    for settings in (
        (Arrangement("missing", "row"),),
        (Arrangement("g", "grid", "center"),),
        (Arrangement("g", "column"),) * 2,
    ):
        with pytest.raises(ValueError):
            replace(p, arrangements=settings)
    with pytest.raises(ValueError):
        replace(p, schema_version=2)


@pytest.mark.minizinc
@pytest.mark.z3
def test_native_engines_do_not_relax_an_impossible_unwrapped_profile():
    from rangekeeper.adapters.cytoscape.layout.minizinc_solver import solve as cp
    from rangekeeper.adapters.cytoscape.layout.z3_solver import solve as z3

    p = replace(fixture("row"), width=150)
    for solve in (z3, cp):
        result = solve(p, optimize=False, allow_relaxed=True, time_limit=5)
        assert result.status == "infeasible", result.reason
        assert not result.rectangles
