import pandas as pd
import pytest

import rangekeeper as rk


def relationship_classification(code="relationship.contains"):
    return rk.graph.Taxonomy(code=code, name=code).define(code=code, name=code)


def tree_graph(*, reverse=False):
    root = rk.graph.Entity(entity_id="root", name="Root")
    branch = rk.graph.Entity(entity_id="branch", name="Branch")
    leaf = rk.graph.Entity(entity_id="leaf", name="Leaf")
    contains = relationship_classification()
    graph = rk.graph.Graph()
    graph.entities.add_all((root, branch, leaf))
    endpoints = (
        (("branch", "root"), ("leaf", "branch"))
        if reverse
        else (("root", "branch"), ("branch", "leaf"))
    )
    graph.relationships.add_all(
        tuple(
            rk.graph.Relationship(
                source,
                target,
                contains,
                relationship_id=f"{source}-{target}",
            )
            for source, target in endpoints
        )
    )
    return graph, root, branch, leaf, contains


def test_numeric_aggregation_is_pure_and_includes_zero():
    graph, root, branch, leaf, _ = tree_graph()
    root.features["gfa"] = 10
    branch.features["gfa"] = 0
    leaf.features["gfa"] = 5

    result = rk.graph.View(graph).aggregate(feature="gfa")

    assert result == {"root": 15, "branch": 5, "leaf": 5}
    assert root.features == {"gfa": 10}
    assert branch.features == {"gfa": 0}
    assert leaf.features == {"gfa": 5}


def test_missing_and_explicit_none_are_absent_but_zero_is_retained():
    root = rk.graph.Entity(entity_id="root")
    zero = rk.graph.Entity(entity_id="zero")
    missing = rk.graph.Entity(entity_id="missing")
    none = rk.graph.Entity(entity_id="none")
    zero.features["value"] = 0
    none.features["value"] = None
    kind = relationship_classification()
    graph = rk.graph.Graph()
    graph.entities.add_all((root, zero, missing, none))
    graph.relationships.add_all(
        tuple(
            rk.graph.Relationship(
                "root", child.entity_id, kind, relationship_id=child.entity_id
            )
            for child in (zero, missing, none)
        )
    )

    result = rk.graph.View(graph).aggregate(feature="value")

    assert result == {"root": 0, "zero": 0, "missing": None, "none": None}


def test_pint_quantities_use_default_numeric_aggregation():
    graph, root, branch, leaf, _ = tree_graph()
    units = rk.measure.Index.registry
    root.features["area"] = 1 * units.sqm
    branch.features["area"] = 2 * units.sqm
    leaf.features["area"] = 30_000 * units.centimeter**2

    result = rk.graph.View(graph).aggregate(feature="area")

    assert result["root"].to(units.sqm).magnitude == pytest.approx(6)
    assert result["branch"].to(units.sqm).magnitude == pytest.approx(5)


def test_into_assignment_overwrites_only_after_success_and_is_idempotent():
    graph, root, branch, leaf, _ = tree_graph()
    root.features["value"] = 1
    branch.features["value"] = 2
    leaf.features["value"] = 3
    for entity in graph.entities.all():
        entity.features["subtotal"] = -1

    first = rk.graph.View(graph).aggregate(feature="value", into="subtotal")
    second = rk.graph.View(graph).aggregate(feature="value", into="subtotal")

    assert first == second == {"root": 6, "branch": 5, "leaf": 3}
    assert root.features["subtotal"] == 6
    assert branch.features["subtotal"] == 5
    assert leaf.features["subtotal"] == 3
    assert [entity.features["value"] for entity in graph.entities.all()] == [1, 2, 3]


def test_into_cannot_overwrite_the_source_feature():
    graph, *_ = tree_graph()

    with pytest.raises(rk.graph.InvalidAggregationError, match="must differ"):
        rk.graph.View(graph).aggregate(feature="value", into="value")


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"feature": ""}, ValueError, "feature"),
        ({"feature": "value", "into": ""}, ValueError, "into"),
        ({"feature": "value", "reduce": 1}, TypeError, "reduce"),
    ],
)
def test_aggregation_request_types_are_validated(arguments, error, message):
    graph, *_ = tree_graph()

    with pytest.raises(error, match=message):
        rk.graph.View(graph).aggregate(**arguments)


def test_callback_failure_does_not_partially_assign_results():
    graph, root, branch, leaf, _ = tree_graph()
    for entity, value in ((root, 1), (branch, 2), (leaf, 3)):
        entity.features["value"] = value
        entity.features["subtotal"] = "unchanged"

    def fail_at_root(entity, values):
        if entity.entity_id == "root":
            raise RuntimeError("failed")
        return sum(values)

    with pytest.raises(RuntimeError, match="failed"):
        rk.graph.View(graph).aggregate(
            feature="value",
            into="subtotal",
            reduce=fail_at_root,
        )

    assert all(
        entity.features["subtotal"] == "unchanged" for entity in graph.entities.all()
    )


def test_custom_callback_receives_entity_and_ordered_values():
    root = rk.graph.Entity(entity_id="root")
    left = rk.graph.Entity(entity_id="left")
    right = rk.graph.Entity(entity_id="right")
    root.features["value"] = "root"
    left.features["value"] = "left"
    right.features["value"] = "right"
    kind = relationship_classification()
    graph = rk.graph.Graph()
    graph.entities.add_all((root, left, right))
    graph.relationships.add_all(
        (
            rk.graph.Relationship("root", "left", kind, relationship_id="left-edge"),
            rk.graph.Relationship("root", "right", kind, relationship_id="right-edge"),
        )
    )
    observed = {}

    def collect(entity, values):
        observed[entity.entity_id] = values
        return "+".join(values)

    result = rk.graph.View(graph).aggregate(feature="value", reduce=collect)

    assert observed["left"] == ("left",)
    assert observed["root"] == ("root", "left", "right")
    assert result["root"] == "root+left+right"


def test_default_aggregation_rejects_values_that_cannot_be_summed():
    graph, root, *_ = tree_graph()
    root.features["value"] = {"amount": 1}

    with pytest.raises(TypeError):
        rk.graph.View(graph).aggregate(feature="value")


def test_aggregation_follows_relationship_source_to_target_direction():
    graph, root, branch, leaf, _ = tree_graph(reverse=True)
    root.features["value"] = 1
    branch.features["value"] = 2
    leaf.features["value"] = 3

    result = rk.graph.View(graph).aggregate(feature="value")

    assert result == {"root": 1, "branch": 3, "leaf": 6}


def test_empty_cycle_and_multi_parent_views_are_rejected_precisely():
    empty_graph = rk.graph.Graph()
    with pytest.raises(rk.graph.InvalidAggregationError, match="empty View"):
        rk.graph.View(empty_graph).aggregate(feature="value")

    kind = relationship_classification()
    cycle_graph = rk.graph.Graph()
    cycle_entities = tuple(
        rk.graph.Entity(entity_id=entity_id) for entity_id in ("a", "b")
    )
    cycle_graph.entities.add_all(cycle_entities)
    cycle_graph.relationships.add_all(
        (
            rk.graph.Relationship("a", "b", kind, relationship_id="a-b"),
            rk.graph.Relationship("b", "a", kind, relationship_id="b-a"),
        )
    )
    with pytest.raises(rk.graph.InvalidAggregationError, match="arborescence"):
        rk.graph.View(cycle_graph).aggregate(feature="value")

    parent_graph = rk.graph.Graph()
    parents = tuple(
        rk.graph.Entity(entity_id=entity_id)
        for entity_id in ("first", "second", "child")
    )
    parent_graph.entities.add_all(parents)
    parent_graph.relationships.add_all(
        (
            rk.graph.Relationship(
                "first", "child", kind, relationship_id="first-child"
            ),
            rk.graph.Relationship(
                "second", "child", kind, relationship_id="second-child"
            ),
        )
    )
    with pytest.raises(rk.graph.InvalidAggregationError, match="arborescence"):
        rk.graph.View(parent_graph).aggregate(feature="value")


def test_relationship_filtered_overlay_can_be_aggregated():
    graph, root, branch, leaf, contains = tree_graph()
    root.features["value"] = 1
    branch.features["value"] = 2
    leaf.features["value"] = 3
    services = relationship_classification("relationship.services")
    graph.relationships.add(
        rk.graph.Relationship("leaf", "root", services, relationship_id="services")
    )

    with pytest.raises(rk.graph.InvalidAggregationError, match="arborescence"):
        rk.graph.View(graph).aggregate(feature="value")

    result = rk.graph.View(graph, relationship_classification=contains).aggregate(
        feature="value"
    )
    assert result["root"] == 6


def test_stream_sum_can_reduce_flow_and_stream_features():
    graph, root, branch, leaf, _ = tree_graph()
    frequency = rk.duration.Type.MONTH
    units = rk.measure.Index.registry.dimensionless

    def flow(name, value):
        return rk.flux.Flow(
            movements=pd.Series(
                [float(value)],
                index=pd.DatetimeIndex(["2030-01-31"]),
                name=name,
            ),
            units=units,
            name=name,
        )

    root.features["cashflow"] = flow("Root Income", 1)
    branch_input = rk.flux.Stream(
        flows=[flow("Branch Income", 2)],
        frequency=frequency,
        name="Branch Input",
    )
    branch.features["cashflow"] = branch_input
    leaf.features["cashflow"] = flow("Leaf Income", 3)

    def sum_flux(entity, values):
        flows = []
        for value in values:
            if isinstance(value, rk.flux.Flow):
                flows.append(value.duplicate())
            elif isinstance(value, rk.flux.Stream):
                flows.extend(flow.duplicate() for flow in value.flows)
            else:
                raise TypeError(type(value).__name__)
        stream = rk.flux.Stream(
            flows=flows,
            frequency=frequency,
            name=f"Cashflow for {entity.name}",
        )
        return stream.sum(name=stream.name)

    first = rk.graph.View(graph).aggregate(
        feature="cashflow",
        into="subtotal_cashflow",
        reduce=sum_flux,
    )
    second = rk.graph.View(graph).aggregate(
        feature="cashflow",
        into="subtotal_cashflow",
        reduce=sum_flux,
    )

    root_result = second["root"]
    assert isinstance(first["root"], rk.flux.Flow)
    assert isinstance(root_result, rk.flux.Flow)
    assert root_result.name == "Cashflow for Root"
    assert root_result.movements.iloc[0] == pytest.approx(6)
    assert first["root"].movements.equals(root_result.movements)
    assert len(branch_input.flows) == 1
    assert root.features["subtotal_cashflow"] is root_result
