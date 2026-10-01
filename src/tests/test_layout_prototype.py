"""Geometric counterexamples and corrupted outputs, not snapshots of solver code."""

from dataclasses import replace
from importlib.util import find_spec
from itertools import combinations

import pytest

from rangekeeper.graph.adapter.cytoscape.layout import (
    Assembly,
    Node,
    Problem,
    Rect,
    check,
)
from rangekeeper.graph.adapter.cytoscape.layout.check import metrics
from rangekeeper.graph.adapter.cytoscape.layout.examples import examples
from rangekeeper.graph.adapter.cytoscape.layout.z3_solver import solve

requires_z3 = pytest.mark.skipif(
    find_spec("z3") is None, reason="Install RK[layout-prototype] for solver tests"
)


@pytest.mark.parametrize(
    "name",
    ["disjoint", "nested", "shared-node", "crossing", "shared-child", "variable-sizes"],
)
@requires_z3
def test_feasibility_preserves_all_memberships(name):
    p = examples()[name]
    r = solve(p, time_limit=5, optimize=False)
    assert r.status == "feasible", r.reason
    assert r.strict_status == "sat" and not check(p, r.rectangles)
    assert set(r.rectangles) == {o.id for o in (*p.nodes, *p.assemblies)}
    assert r.measurements["false_enclosures"] == 0


@requires_z3
def test_impossible_is_not_a_solver_timeout_and_fallback_is_explicit():
    p = examples()["impossible-five"]
    strict = solve(p, time_limit=5, optimize=False)
    assert strict.status == "infeasible" and not strict.rectangles
    relaxed = solve(p, time_limit=5, allow_relaxed=True)
    assert relaxed.strict_status == "unsat" and relaxed.mode == "diagnostic"
    assert relaxed.status in {"feasible", "optimal"}
    assert relaxed.findings and all(f["code"] == "exclusion" for f in relaxed.findings)
    assert relaxed.measurements["false_enclosures"] >= 1
    assert relaxed.phases[0]["lower_bound"] >= 1


@requires_z3
def test_unknown_has_no_stale_geometry_or_infeasibility_claim():
    r = solve(examples()["nested"], resource_limit=1, allow_relaxed=True)
    assert r.status == "unknown" and r.strict_status == "unknown"
    assert r.mode == "strict" and not r.rectangles
    assert r.reason


@requires_z3
def test_bounded_infeasible_can_be_fixed_by_larger_canvas():
    p = Problem((Node("n", "Node", 100, 40),), (), width=90, height=60)
    assert solve(p).status == "infeasible"
    assert solve(replace(p, width=120)).status == "optimal"


def test_grid_score_is_spacing_not_just_integer_coordinates():
    p = Problem(
        (Node("a", "A", 40, 20), Node("b", "B", 40, 20)),
        (Assembly("g", "Group", ("a", "b")),),
    )
    good = {
        "g": Rect(0, 0, 180, 100),
        "a": Rect(16, 44, 40, 20),
        "b": Rect(68, 44, 40, 20),
    }
    grids = {"g": {"x": 16, "y": 44, "columns": 2}}
    assert not check(p, good)
    assert metrics(p, good, grids)["grid_displacement"] == 0
    bad_grid = {**good, "b": Rect(76, 47, 40, 20)}
    assert not check(p, bad_grid)
    assert metrics(p, bad_grid, grids)["grid_displacement"] == 11


def test_checker_detects_partial_intersection_not_only_centre():
    p = Problem((Node("n", "Node", 40, 20),), (Assembly("g", "Empty", ()),), gap=0)
    # Centre of n is outside g, but 10px of its body is inside.
    out = {"n": Rect(10, 70, 40, 20), "g": Rect(40, 0, 140, 100)}
    assert "exclusion" in {f.code for f in check(p, out)}


def test_nested_ancestor_is_not_a_false_enclosure():
    p = Problem(
        (Node("n", "Node", 40, 20),),
        (Assembly("inner", "Inner", ("n",)), Assembly("outer", "Outer", ("inner",))),
    )
    out = {
        "outer": Rect(0, 0, 220, 180),
        "inner": Rect(16, 44, 140, 100),
        "n": Rect(32, 88, 40, 20),
    }
    assert not check(p, out)


@requires_z3
def test_checker_rejects_mutations_to_identity_size_containment_and_collision():
    p = examples()["shared-node"]
    r = solve(p, optimize=False)
    assert r.status == "feasible"
    missing = dict(r.rectangles)
    missing.pop("s")
    assert any(f.code == "missing" for f in check(p, missing))
    changed = dict(r.rectangles)
    changed["s"] = replace(changed["s"], width=1)
    assert any(f.code == "size" for f in check(p, changed))
    changed = dict(r.rectangles)
    changed["s"] = replace(changed["s"], x=p.width)
    assert any(f.code == "containment" for f in check(p, changed))
    changed = dict(r.rectangles)
    changed["a"] = replace(changed["a"], x=changed["s"].x, y=changed["s"].y)
    assert any(f.code == "collision" for f in check(p, changed))


@requires_z3
def test_grid_includes_child_assemblies_and_checker_matches_solver():
    r = solve(examples()["nested"], time_limit=2)
    assert r.status in {"feasible", "optimal"}
    assert "root" in r.grids
    assert r.phases[0]["value"] == r.measurements["false_enclosures"]


@requires_z3
def test_pins_are_enforced_and_checked():
    p = Problem((Node("a", "A"),), (), pins=(("a", 100, 80),))
    r = solve(p)
    assert (r.rectangles["a"].x, r.rectangles["a"].y) == (100, 80)
    assert any(f.code == "pin" for f in check(p, {"a": Rect(0, 0, 96, 40)}))


def test_invalid_contracts_rejected():
    for make in [
        lambda: Problem((Node("a", "A"), Node("a", "Other")), ()),
        lambda: Problem((), (Assembly("g", "G", ("missing",)),)),
        lambda: Problem((), (Assembly("g", "G", ("g",)),)),
        lambda: Problem((Node("a", "A", 0),), ()),
    ]:
        with pytest.raises(ValueError):
            make()


@requires_z3
def test_five_counterexample_all_four_subsets_are_feasible():
    # Remove one of the five four-of-five requirements: the obstruction disappears.
    p = examples()["impossible-five"]
    for assemblies in combinations(p.assemblies, 4):
        r = solve(replace(p, assemblies=assemblies), time_limit=5, optimize=False)
        assert r.status == "feasible", r.reason
        assert not check(replace(p, assemblies=assemblies), r.rectangles)


@requires_z3
def test_svg_preserves_geometry_and_rejects_duplicate_visual_instances():
    from rangekeeper.graph.adapter.cytoscape.layout.render import svg, verify_svg

    p = Problem((Node("a", "<unsafe>& label"),), ())
    r = solve(p)
    source = svg(p, r)
    assert "&lt;unsafe&gt;" in source
    assert not verify_svg(p, source, r.rectangles)
    duplicate = source.replace(
        "</svg>", '<rect data-object="a" x="0" y="0" width="96" height="40"/></svg>', 1
    )
    with pytest.raises(ValueError, match="Duplicate"):
        verify_svg(p, duplicate, r.rectangles)
    shifted = source.replace('data-kind="node" x="0"', 'data-kind="node" x="1"')
    with pytest.raises(ValueError, match="coordinates"):
        verify_svg(p, shifted, r.rectangles)


def test_unrelated_assembly_cannot_be_fully_enclosed_but_can_intersect():
    p = Problem((), (Assembly("a", "A", ()), Assembly("b", "B", ())))
    enclosed = {"a": Rect(0, 0, 300, 200), "b": Rect(16, 44, 140, 80)}
    assert any(
        f.code == "exclusion" and f.objects == ("b", "a") for f in check(p, enclosed)
    )
    intersecting = {"a": Rect(0, 0, 300, 100), "b": Rect(160, 44, 180, 100)}
    assert not check(p, intersecting)
