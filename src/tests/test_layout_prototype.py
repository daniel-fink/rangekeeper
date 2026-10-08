"""Geometric counterexamples and corrupted outputs, not snapshots of solver code."""

from rangekeeper.adapters.cytoscape.layout.result import (
    ResultMode,
    ResultStatus,
    StrictStatus,
)
from dataclasses import replace
from itertools import combinations

import pytest

from rangekeeper.adapters.cytoscape.layout import Assembly, Node, Problem, Rect, check
from rangekeeper.adapters.cytoscape.layout.check import metrics
from rangekeeper_examples.layout import examples
from rangekeeper.adapters.cytoscape.layout.z3_solver import solve

requires_z3 = pytest.mark.z3


@pytest.mark.parametrize(
    "name",
    ["disjoint", "nested", "shared-node", "crossing", "shared-child", "variable-sizes"],
)
@requires_z3
def test_feasibility_preserves_all_memberships(name):
    p = examples()[name]
    r = solve(p, time_limit=5, optimize=False)
    assert r.status == ResultStatus.FEASIBLE, r.reason
    assert r.strict_status == StrictStatus.SAT and not check(p, r.rectangles)
    assert set(r.rectangles) == {o.id for o in (*p.nodes, *p.assemblies)}
    assert r.measurements["false_enclosures"] == 0


@requires_z3
def test_impossible_is_not_a_solver_timeout_and_fallback_is_explicit():
    p = examples()["impossible-five"]
    strict = solve(p, time_limit=5, optimize=False)
    assert strict.status == ResultStatus.INFEASIBLE and not strict.rectangles
    relaxed = solve(p, time_limit=5, allow_relaxed=True)
    assert (
        relaxed.strict_status == StrictStatus.UNSAT
        and relaxed.mode == ResultMode.DIAGNOSTIC
    )
    assert relaxed.status in {ResultStatus.FEASIBLE, ResultStatus.OPTIMAL}
    assert relaxed.findings and all(f["code"] == "exclusion" for f in relaxed.findings)
    assert relaxed.measurements["false_enclosures"] >= 1
    assert relaxed.phases[0]["lower_bound"] >= 1


@requires_z3
def test_unknown_has_no_stale_geometry_or_infeasibility_claim():
    r = solve(examples()["nested"], resource_limit=1, allow_relaxed=True)
    assert r.status == ResultStatus.UNKNOWN and r.strict_status == StrictStatus.UNKNOWN
    assert r.mode == ResultMode.STRICT and not r.rectangles
    assert r.reason


@requires_z3
def test_bounded_infeasible_can_be_fixed_by_larger_canvas():
    p = Problem((Node("n", "Node", 100, 40),), (), width=90, height=60)
    assert solve(p).status == ResultStatus.INFEASIBLE
    assert solve(replace(p, width=120)).status == ResultStatus.OPTIMAL


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
    assert r.status == ResultStatus.FEASIBLE
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
    assert r.status in {ResultStatus.FEASIBLE, ResultStatus.OPTIMAL}
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
        assert r.status == ResultStatus.FEASIBLE, r.reason
        assert not check(replace(p, assemblies=assemblies), r.rectangles)


@requires_z3
def test_svg_preserves_geometry_and_rejects_duplicate_visual_instances():
    from rangekeeper.adapters.cytoscape.layout.render import svg, verify_svg

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


def test_descendant_index_handles_shared_subgraphs_and_detaches_results():
    p = examples()["shared-child"]
    index = p.descendant_index()
    assert index == {a.id: p.descendants(a.id) for a in p.assemblies}
    groups = {a.id: a for a in p.assemblies}
    for a in p.assemblies:
        expected = set(a.members)
        pending = list(a.members)
        while pending:
            node = pending.pop()
            for child in groups[node].members if node in groups else ():
                if child not in expected:
                    expected.add(child)
                    pending.append(child)
        assert index[a.id] == expected
    index.clear()
    assert p.descendant_index()


def test_assessment_checks_once_and_preserves_independent_metrics(monkeypatch):
    import importlib

    checker = importlib.import_module("rangekeeper.adapters.cytoscape.layout.check")
    p = Problem((Node("n", "Node", 40, 20),), ())
    rectangles = {"n": Rect(12, 12, 40, 20)}
    expected = metrics(p, rectangles, {})
    original = checker.check
    calls = []

    def counted(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(checker, "check", counted)
    findings, measured = checker.assess(p, rectangles, {})
    assert not findings and measured == expected
    assert len(calls) == 1
    # Incomplete candidates retain findings without trying to measure absent geometry.
    findings, measured = checker.assess(p, {}, {})
    assert [f.code for f in findings] == ["missing"] and measured == {}
    assert len(calls) == 2
    with pytest.raises(ValueError):
        checker.metrics(p, {}, {})


def test_descendant_index_walks_a_deep_chain_without_recursion():
    depth = 1100
    groups = tuple(
        Assembly(str(i), str(i), (str(i - 1) if i else "leaf",)) for i in range(depth)
    )
    problem = Problem((Node("leaf", "Leaf", 1, 1),), groups)
    index = problem.descendant_index()
    assert index["0"] == {"leaf"}
    assert index[str(depth - 1)] == {"leaf", *(str(i) for i in range(depth - 1))}


def test_formulations_and_renderer_prepare_topology_once(monkeypatch):
    from rangekeeper.adapters.cytoscape.layout.minizinc_data import encode
    from rangekeeper.adapters.cytoscape.layout.render import svg
    from rangekeeper.adapters.cytoscape.layout.result import Result
    from rangekeeper.adapters.cytoscape.layout.z3_model import Formulation

    problem = Problem((Node("n", "Node", 40, 20),), ())
    original = Problem.descendant_index
    calls = []

    def counted(self):
        calls.append(self)
        return original(self)

    monkeypatch.setattr(Problem, "descendant_index", counted)
    encode(problem, None)
    assert len(calls) == 1
    Formulation(problem)
    assert len(calls) == 2
    result = Result(
        status=ResultStatus.FEASIBLE,
        strict_status=StrictStatus.SAT,
        problem_fingerprint=problem.fingerprint,
    )
    result.rectangles = {"n": Rect(12, 12, 40, 20)}
    svg(problem, result)
    # The emitted SVG has its own independent read-back validation boundary.
    assert len(calls) == 4
