"""Cross-engine geometry and score parity, including failure semantics."""

from rangekeeper.adapters.cytoscape.layout.model import Axis, PreferenceDirection
from rangekeeper.adapters.cytoscape.layout.result import (
    ResultMode,
    ResultStatus,
    StrictStatus,
)
from dataclasses import replace

import pytest

from rangekeeper.adapters.cytoscape.layout import Assembly, Node, Problem, Rect
from rangekeeper.adapters.cytoscape.layout.check import check
from rangekeeper_examples.layout import examples
from rangekeeper.adapters.cytoscape.layout.minizinc_solver import solve
from rangekeeper.adapters.cytoscape.layout.model import Preference, Weights
from rangekeeper.adapters.cytoscape.layout.seed import grid_seed
from rangekeeper.adapters.cytoscape.layout.z3_solver import solve as z3_solve

pytestmark = pytest.mark.minizinc


@pytest.mark.parametrize(
    "name",
    ["disjoint", "nested", "shared-node", "crossing", "shared-child", "variable-sizes"],
)
def test_feasible_shared_and_nested_memberships(name):
    p = examples()[name]
    r = solve(p, time_limit=5, optimize=False)
    assert r.status == ResultStatus.FEASIBLE, r.reason
    assert r.strict_status == StrictStatus.SAT and not check(p, r.rectangles)


def test_infeasible_and_unknown_have_distinct_fallbacks():
    impossible = Problem((Node("n", "N", 100, 40),), (), width=90, height=60)
    assert solve(impossible, time_limit=2).status == ResultStatus.INFEASIBLE
    assert (
        solve(replace(impossible, width=120), time_limit=2).status
        == ResultStatus.OPTIMAL
    )
    r = solve(examples()["nested"], time_limit=1e-6, allow_relaxed=True)
    assert r.status is ResultStatus.UNKNOWN
    assert r.strict_status is StrictStatus.UNKNOWN
    assert r.mode == ResultMode.STRICT and not r.rectangles
    r = solve(
        examples()["impossible-five"], time_limit=8, allow_relaxed=True, optimize=False
    )
    assert r.strict_status == StrictStatus.UNSAT and r.mode == ResultMode.DIAGNOSTIC
    assert r.status == ResultStatus.FEASIBLE and r.findings
    assert all(f["code"] == "exclusion" for f in r.findings)


@pytest.mark.z3
@pytest.mark.parametrize("direction", tuple(PreferenceDirection))
def test_fixed_seed_scores_match_both_engines(direction):
    p = Problem(
        tuple(Node(i, i, 24 + 10 * k, 20) for k, i in enumerate("abcd")),
        (Assembly("g", "G", tuple("abcd"), 100), Assembly("root", "Root", ("g",), 100)),
        width=800,
        height=800,
        weights=Weights(),
        preferences=(
            Preference(
                "g",
                direction,
                orders=(("a", "b", Axis.X), ("b", "a", Axis.X), ("c", "d", Axis.Y)),
                affinities=(("a", "c", 37), ("b", "d", 100)),
                strength=3,
            ),
        ),
    )
    seed = grid_seed(p)
    assert seed is not None
    assert seed
    # A displaced grid origin gives a nonzero displacement without changing geometry.
    seed.grids["g"]["x"] += 1
    a = z3_solve(p, initial=seed, optimize=False, time_limit=5)
    b = solve(p, initial=seed, optimize=False, time_limit=5)
    assert a.status == b.status == ResultStatus.FEASIBLE
    assert a.rectangles == b.rectangles == seed.rectangles
    assert a.grids == b.grids == seed.grids
    assert a.measurements == b.measurements
    assert a.measurements["grid_score"] > 0


@pytest.mark.z3
@pytest.mark.parametrize("flexible", [False, True])
def test_tiny_optima_match(flexible):
    p = Problem(
        (Node("a", "A", 8, 6), Node("b", "B", 8, 6)),
        (Assembly("g", "G", ("a", "b"), 12),),
        width=50,
        height=40,
        padding=2,
        header=4,
        gap=2,
        weights=Weights() if flexible else None,
        preferences=(
            (
                Preference(
                    "g",
                    PreferenceDirection.HORIZONTAL,
                    orders=(("a", "b", Axis.X),),
                    affinities=(("a", "b", 100),),
                ),
            )
            if flexible
            else ()
        ),
    )
    a = z3_solve(p, time_limit=10)
    b = solve(p, time_limit=10)
    assert a.status == b.status == ResultStatus.OPTIMAL
    assert [(v["objective"], v["value"]) for v in a.phases] == [
        (v["objective"], v["value"]) for v in b.phases
    ]


def test_seed_validation_and_pins():
    p = Problem((Node("n", "N"),), (), pins=(("n", 100, 80),))
    r = solve(p, time_limit=3)
    assert r.status == ResultStatus.OPTIMAL and r.rectangles["n"] == Rect(
        100, 80, 96, 40
    )
    seed = grid_seed(replace(examples()["nested"], weights=Weights()))
    with pytest.raises(ValueError, match="match"):
        solve(p, initial=seed)


def test_checked_seed_survives_timeout_without_claiming_native_solution():
    p = replace(examples()["nested"], weights=Weights())
    seed = grid_seed(p)
    assert seed is not None
    r = solve(p, initial=seed, time_limit=1e-6)
    assert r.status == ResultStatus.FEASIBLE and r.incumbent_source == "checked_seed"
    assert r.first_solution_seconds is None and r.rectangles == seed.rectangles
    assert not r.phases[-1]["proven"]


def test_warm_start_is_a_hint_not_a_position_constraint():
    from copy import deepcopy

    p = Problem(
        (Node("a", "A", 20, 10), Node("b", "B", 20, 10)),
        (Assembly("g", "G", ("a", "b"), 30),),
        width=400,
        height=400,
        weights=Weights(),
        padding=4,
        header=8,
        gap=4,
    )
    seed = grid_seed(p)
    assert seed is not None
    seed.rectangles = {
        i: replace(r, x=r.x + 80, y=r.y + 80) for i, r in seed.rectangles.items()
    }
    seed.grids = {
        i: {**g, "x": g["x"] + 80, "y": g["y"] + 80} for i, g in seed.grids.items()
    }
    before = deepcopy(seed)
    r = solve(p, initial=seed, time_limit=4)
    assert r.incumbent_source == "solver" and r.status == ResultStatus.OPTIMAL
    assert r.measurements["extent"] < max(
        v.right for v in seed.rectangles.values()
    ) + max(v.bottom for v in seed.rectangles.values())
    assert seed == before


def test_native_backend_receives_warm_start_annotations(tmp_path):
    import json
    import subprocess
    from pathlib import Path

    from rangekeeper.adapters.cytoscape.layout import minizinc_solver

    p = Problem(
        (Node("a", "A", 20, 10), Node("b", "B", 20, 10)),
        (Assembly("g", "G", ("a", "b"), 30),),
        width=400,
        height=400,
        weights=Weights(),
        padding=4,
        header=8,
        gap=4,
    )
    seed = grid_seed(p)
    assert seed is not None
    data, _, _ = minizinc_solver.encode(p, seed)
    data.update(fixed=False, phase=9, incumbent_bound=seed.measurements["style_cost"])
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    binary = minizinc_solver.toolchain()["executable"]
    run = subprocess.run(
        [
            binary,
            "--solver",
            "cp-sat",
            "-p",
            "1",
            "-f",
            "--params",
            "log_search_progress:true",
            "--time-limit",
            "2000",
            str(Path(minizinc_solver.__file__).with_name("assembly.mzn")),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    # A warm_start_array wrapper was silently ignored. Actual native ingestion
    # is the regression boundary; an emitted annotation alone is insufficient.
    assert "solution hint is" in (run.stdout + run.stderr).lower()


def test_neighborhood_improves_global_score_without_moving_outside_or_claiming_global_optimum():
    from rangekeeper.adapters.cytoscape.layout.check import metrics
    from rangekeeper.adapters.cytoscape.layout.refine import refine
    from rangekeeper.adapters.cytoscape.layout.result import Result

    p = Problem(
        tuple(Node(i, i, 20, 10) for i in "abc"),
        (Assembly("g", "G", ("a", "b"), 40), Assembly("root", "Root", ("g", "c"), 80)),
        width=300,
        height=200,
        padding=4,
        header=8,
        gap=4,
        weights=Weights(),
    )
    rects = {
        "root": Rect(0, 0, 200, 100),
        "g": Rect(4, 12, 80, 50),
        "a": Rect(8, 24, 20, 10),
        "b": Rect(36, 24, 20, 10),
        "c": Rect(100, 12, 20, 10),
    }
    grids = {
        "g": {"x": 8, "y": 24, "columns": 2, "slots": {"a": 0, "b": 1}},
        "root": {"x": 4, "y": 12, "columns": 2, "slots": {"g": 0, "c": 1}},
    }
    assert not check(p, rects)
    initial = Result(
        ResultStatus.FEASIBLE,
        StrictStatus.SAT,
        rectangles=rects,
        grids=grids,
        problem_fingerprint=p.fingerprint,
    )
    before = metrics(p, rects, grids)
    result = refine(p, initial, time_limit=4, region_limit=3, max_regions=1)
    assert (
        result.status == ResultStatus.FEASIBLE
        and result.incumbent_source == "neighborhood_solver"
    )
    assert result.measurements["style_cost"] < before["style_cost"]
    assert not check(p, result.rectangles)
    assert all(result.rectangles[i] == rects[i] for i in ("root", "g", "c"))
    assert result.search_scope["mode"] == "bounded_neighborhoods"
    assert result.solver_statistics[0]["accepted"]
    phases = result.solver_statistics[0]["phases"]
    assert all(not phase["proven"] for phase in phases if phase["value"] > 0)
