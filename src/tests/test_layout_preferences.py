"""Evidence normalization, soft conflicting intent and independent geometry scores."""

from dataclasses import replace
from importlib.util import find_spec

import pytest

from uuid import uuid4
from rangekeeper.model import (
    Model,
    Metadata,
    System,
    Characteristics,
    Definitions,
    Entity,
    Value,
    Quantity,
    Measure,
)
from rangekeeper.model.content import encode

from rangekeeper.adapters.cytoscape.layout import (
    Assembly,
    Node,
    Preference,
    Problem,
    Weights,
    check,
)
from rangekeeper.adapters.cytoscape.layout.check import metrics
from rangekeeper.adapters.cytoscape.layout.model import Rect, from_document
from rangekeeper.adapters.cytoscape.layout.seed import grid_seed
from rangekeeper.adapters.cytoscape.layout.similarity import Signal, affinities
from rangekeeper.adapters.cytoscape.layout.z3_solver import solve


requires_z3 = pytest.mark.skipif(
    find_spec("z3") is None, reason="Optional Z3 dependency"
)


def graph_records(records):
    return Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
        system=System(
            entities=tuple(
                Entity(
                    id=uuid4(),
                    code=str(i),
                    characteristics=Characteristics(
                        values=tuple(
                            Value(id=uuid4(), key=k, kind="property", content=encode(v))
                            for k, v in row.items()
                        )
                    ),
                )
                for i, row in enumerate(records)
            )
        ),
    )


def test_similarity_normalizes_numeric_range_and_does_not_cluster_missing_values():
    graph = graph_records(
        [
            {"size": 100, "category": "A"},
            {"size": 110, "category": "A"},
            {"size": 200, "category": "B"},
            {"size": None},
            {"size": None},
        ]
    )
    ids = tuple(str(e.id) for e in graph.find_entities())
    signals = (
        Signal("property", "size", "numeric", "size"),
        Signal("property", "category", "category", "category"),
    )
    edges, report = affinities(graph, ids, signals)
    assert {frozenset((i, j)): w for i, j, w in edges} == {frozenset(ids[:2]): 95}
    assert all(
        p["strength"] == 0
        for p in report["pairs"]
        if p["left"] in ids[3:] or p["right"] in ids[3:]
    )
    assert all(c["missing"] == 2 for c in report["columns"])


def test_partial_observations_do_not_become_perfect_matches():
    graph = graph_records([{"x": 0, "y": 0}, {"x": 0, "y": None}, {"x": 1, "y": 1}])
    ids = tuple(str(e.id) for e in graph.find_entities())
    edges, report = affinities(
        graph,
        ids,
        (
            Signal("property", "x", "numeric", "x"),
            Signal("property", "y", "numeric", "y"),
        ),
    )
    assert not edges
    pair = next(p for p in report["pairs"] if {p["left"], p["right"]} == set(ids[:2]))
    assert pair["strength"] == 50


def test_constant_signals_identifiers_and_redundant_families():
    graph = graph_records([{"same": "A"}, {"same": "A"}])
    ids = tuple(str(e.id) for e in graph.find_entities())
    signal = Signal("property", "same", "category", "type")
    assert not affinities(graph, ids, (signal,))[0]
    assert not affinities(graph, ids, ())[0]  # Object code is never an implicit signal.
    with pytest.raises(ValueError, match="one signal"):
        affinities(graph, ids, (signal, replace(signal, key="other")))


def test_measurement_units_are_normalized_before_similarity():
    m = Measure(id=uuid4(), code="length", name="Length", units="meter")
    quantities = (
        Quantity(magnitude=1, units="meter"),
        Quantity(magnitude=100, units="centimeter"),
        Quantity(magnitude=2, units="meter"),
    )
    graph = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
        definitions=Definitions(measures=(m,)),
        system=System(
            entities=tuple(
                Entity(
                    id=uuid4(),
                    characteristics=Characteristics(
                        values=(
                            Value(
                                id=uuid4(),
                                key="length",
                                kind="measurement",
                                measure=m.id,
                                quantity=q,
                            ),
                        )
                    ),
                )
                for q in quantities
            )
        ),
    )
    ids = tuple(str(e.id) for e in graph.find_entities())
    edges, report = affinities(
        graph, ids, (Signal("quantity", "length", "numeric", "size", units="meter"),)
    )
    assert {frozenset((i, j)): w for i, j, w in edges} == {frozenset(ids[:2]): 100}
    assert report["columns"][0]["unit"] == "meter"


def small(direction="horizontal"):
    return Problem(
        tuple(Node(i, i, 40, 24) for i in "abcd"),
        (Assembly("g", "Group", tuple("abcd")),),
        weights=Weights(),
        preferences=(Preference("g", direction=direction),),
    )


def test_direction_changes_checked_seed_without_changing_membership():
    horizontal, vertical = small(), small("vertical")
    h, v = grid_seed(horizontal), grid_seed(vertical)
    assert h and v
    assert not check(horizontal, h.rectangles) and not check(vertical, v.rectangles)
    assert h.measurements["width"] > h.measurements["height"]
    assert v.measurements["height"] > v.measurements["width"]
    assert h.measurements["direction_score"] == v.measurements["direction_score"] == 0
    assert horizontal.assemblies == vertical.assemblies


def test_grid_permutation_is_checked_and_can_exchange_members():
    p = small()
    r = grid_seed(p)
    assert r
    swapped = dict(r.rectangles)
    swapped["a"], swapped["d"] = swapped["d"], swapped["a"]
    grids = {"g": {**r.grids["g"], "slots": dict(r.grids["g"]["slots"])}}
    grids["g"]["slots"]["a"], grids["g"]["slots"]["d"] = (
        grids["g"]["slots"]["d"],
        grids["g"]["slots"]["a"],
    )
    assert metrics(p, swapped, grids)["grid_score"] == 0
    grids["g"]["slots"]["a"] = grids["g"]["slots"]["d"]
    with pytest.raises(ValueError, match="permutation"):
        metrics(p, swapped, grids)


def test_shared_members_do_not_get_a_tree_seed_or_new_memberships():
    p = Problem(
        (Node("s", "Shared"), Node("a", "A"), Node("b", "B")),
        (Assembly("floor", "Floor", ("a", "s")), Assembly("core", "Core", ("s", "b"))),
        weights=Weights(),
        preferences=(Preference("floor", "horizontal"), Preference("core", "vertical")),
    )
    assert grid_seed(p) is None


@requires_z3
def test_conflicting_orders_are_soft_and_checker_matches_every_score():
    p = replace(
        small(),
        preferences=(
            Preference(
                "g",
                "horizontal",
                orders=(("a", "b", "x"), ("b", "a", "x")),
                affinities=(("a", "c", 100),),
            ),
        ),
    )
    seed = grid_seed(p)
    assert seed
    r = solve(p, time_limit=2, initial=seed)
    assert r.status in {"feasible", "optimal"} and not check(p, r.rectangles)
    assert r.measurements["order_score"] > 0
    assert r.measurements["style_cost"] <= seed.measurements["style_cost"]
    assert r.measurements == metrics(p, r.rectangles, r.grids)


@requires_z3
def test_direction_and_similarity_keep_shared_membership_feasible():
    p = Problem(
        (Node("s", "Shared", 40, 24), Node("a", "A", 40, 24), Node("b", "B", 40, 24)),
        (Assembly("floor", "Floor", ("a", "s")), Assembly("core", "Core", ("s", "b"))),
        weights=Weights(),
        preferences=(
            Preference("floor", "horizontal", affinities=(("a", "s", 100),)),
            Preference("core", "vertical"),
        ),
    )
    r = solve(p, time_limit=3, optimize=False)
    assert r.status == "feasible" and not check(p, r.rectangles)
    assert set(r.rectangles) == {"s", "a", "b", "floor", "core"}


def test_preference_validation_rejects_nonmember_affinity():
    with pytest.raises(ValueError, match="direct members"):
        replace(
            small(), preferences=(Preference("g", affinities=(("a", "missing", 100),)),)
        )
    with pytest.raises(ValueError, match="weights"):
        replace(small(), weights=None)
    with pytest.raises(ValueError, match="Weights"):
        replace(small(), weights=Weights(grid=-1))


def test_empty_assemblies_have_no_direction_penalty():
    p = Problem(
        (),
        (Assembly("empty", "Empty", ()),),
        weights=Weights(),
        preferences=(Preference("empty", "vertical"),),
    )
    r = grid_seed(p)
    assert r
    assert not check(p, r.rectangles) and r.measurements["direction_score"] == 0


def test_proximity_uses_visible_gap_not_label_width():
    p = Problem(
        (Node("a", "A", 248, 44), Node("b", "B", 248, 44)),
        (Assembly("g", "Group", ("a", "b")),),
        weights=Weights(),
        preferences=(Preference("g", "horizontal", affinities=(("a", "b", 100),)),),
    )
    horizontal = {
        "a": Rect(16, 44, 248, 44),
        "b": Rect(276, 44, 248, 44),
        "g": Rect(0, 0, 540, 104),
    }
    vertical = {
        "a": Rect(16, 44, 248, 44),
        "b": Rect(16, 100, 248, 44),
        "g": Rect(0, 0, 280, 160),
    }

    def score(rectangles, columns):
        assert not check(p, rectangles)
        return metrics(
            p,
            rectangles,
            {"g": {"x": 16, "y": 44, "columns": columns, "slots": {"a": 0, "b": 1}}},
        )

    h, v = score(horizontal, 2), score(vertical, 1)
    assert h["similarity_score"] == v["similarity_score"] == 12
    assert h["direction_score"] == 0 and v["direction_score"] > 0


def test_versioned_preferences_roundtrip_and_unknown_fields_fail():
    p = small()
    restored = from_document(p.document())
    assert restored == p and restored.fingerprint == p.fingerprint
    with pytest.raises(ValueError, match="schema"):
        from_document({**p.document(), "schema": "unknown"})
    with pytest.raises(TypeError):
        from_document({**p.document(), "unrecognized": True})
