import pandas as pd
import pytest

import rangekeeper as rk


def relationship_classification(code="relationship.contains"):
    return rk.graph.Classification(code=code, name=code, scheme="project")


def tree_model(*, reverse=False):
    root = rk.graph.Entity(entity_id="root", name="Root")
    branch = rk.graph.Entity(entity_id="branch", name="Branch")
    leaf = rk.graph.Entity(entity_id="leaf", name="Leaf")
    contains = relationship_classification()
    model = rk.graph.Model()
    model.add_entities((root, branch, leaf))
    endpoints = (
        (("branch", "root"), ("leaf", "branch"))
        if reverse
        else (("root", "branch"), ("branch", "leaf"))
    )
    model.add_relationships(
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
    return model, root, branch, leaf, contains


def test_numeric_aggregation_is_pure_and_includes_zero():
    model, root, branch, leaf, _ = tree_model()
    root.features["gfa"] = 10
    branch.features["gfa"] = 0
    leaf.features["gfa"] = 5

    result = model.aggregate(view=model.view(), feature="gfa")

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
    model = rk.graph.Model()
    model.add_entities((root, zero, missing, none))
    model.add_relationships(
        tuple(
            rk.graph.Relationship(
                "root", child.entity_id, kind, relationship_id=child.entity_id
            )
            for child in (zero, missing, none)
        )
    )

    result = model.aggregate(view=model.view(), feature="value")

    assert result == {"root": 0, "zero": 0, "missing": None, "none": None}


def test_pint_quantities_use_default_numeric_aggregation():
    model, root, branch, leaf, _ = tree_model()
    units = rk.measure.Index.registry
    root.features["area"] = 1 * units.sqm
    branch.features["area"] = 2 * units.sqm
    leaf.features["area"] = 30_000 * units.centimeter**2

    result = model.aggregate(view=model.view(), feature="area")

    assert result["root"].to(units.sqm).magnitude == pytest.approx(6)
    assert result["branch"].to(units.sqm).magnitude == pytest.approx(5)


def test_into_assignment_overwrites_only_after_success_and_is_idempotent():
    model, root, branch, leaf, _ = tree_model()
    root.features["value"] = 1
    branch.features["value"] = 2
    leaf.features["value"] = 3
    for entity in model.entities():
        entity.features["subtotal"] = -1

    first = model.aggregate(view=model.view(), feature="value", into="subtotal")
    second = model.aggregate(view=model.view(), feature="value", into="subtotal")

    assert first == second == {"root": 6, "branch": 5, "leaf": 3}
    assert root.features["subtotal"] == 6
    assert branch.features["subtotal"] == 5
    assert leaf.features["subtotal"] == 3
    assert [entity.features["value"] for entity in model.entities()] == [1, 2, 3]


def test_into_cannot_overwrite_the_source_feature():
    model, *_ = tree_model()

    with pytest.raises(rk.graph.InvalidAggregationError, match="must differ"):
        model.aggregate(view=model.view(), feature="value", into="value")


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"feature": ""}, ValueError, "feature"),
        ({"feature": "value", "into": ""}, ValueError, "into"),
        ({"feature": "value", "reduce": 1}, TypeError, "reduce"),
    ],
)
def test_aggregation_request_types_are_validated(arguments, error, message):
    model, *_ = tree_model()

    with pytest.raises(error, match=message):
        model.aggregate(view=model.view(), **arguments)


def test_callback_failure_does_not_partially_assign_results():
    model, root, branch, leaf, _ = tree_model()
    for entity, value in ((root, 1), (branch, 2), (leaf, 3)):
        entity.features["value"] = value
        entity.features["subtotal"] = "unchanged"

    def fail_at_root(entity, values):
        if entity.entity_id == "root":
            raise RuntimeError("failed")
        return sum(values)

    with pytest.raises(RuntimeError, match="failed"):
        model.aggregate(
            view=model.view(),
            feature="value",
            into="subtotal",
            reduce=fail_at_root,
        )

    assert all(
        entity.features["subtotal"] == "unchanged" for entity in model.entities()
    )


def test_custom_callback_receives_entity_and_ordered_values():
    root = rk.graph.Entity(entity_id="root")
    left = rk.graph.Entity(entity_id="left")
    right = rk.graph.Entity(entity_id="right")
    root.features["value"] = "root"
    left.features["value"] = "left"
    right.features["value"] = "right"
    kind = relationship_classification()
    model = rk.graph.Model()
    model.add_entities((root, left, right))
    model.add_relationships(
        (
            rk.graph.Relationship("root", "left", kind, relationship_id="left-edge"),
            rk.graph.Relationship("root", "right", kind, relationship_id="right-edge"),
        )
    )
    observed = {}

    def collect(entity, values):
        observed[entity.entity_id] = values
        return "+".join(values)

    result = model.aggregate(view=model.view(), feature="value", reduce=collect)

    assert observed["left"] == ("left",)
    assert observed["root"] == ("root", "left", "right")
    assert result["root"] == "root+left+right"


def test_default_aggregation_rejects_rich_values_with_guidance():
    model, root, *_ = tree_model()
    root.features["value"] = {"amount": 1}

    with pytest.raises(TypeError, match="provide reduce"):
        model.aggregate(view=model.view(), feature="value")


def test_aggregation_follows_relationship_source_to_target_direction():
    model, root, branch, leaf, _ = tree_model(reverse=True)
    root.features["value"] = 1
    branch.features["value"] = 2
    leaf.features["value"] = 3

    result = model.aggregate(view=model.view(), feature="value")

    assert result == {"root": 1, "branch": 3, "leaf": 6}


def test_empty_cycle_and_multi_parent_views_are_rejected_precisely():
    empty_model = rk.graph.Model()
    with pytest.raises(rk.graph.InvalidAggregationError, match="empty View"):
        empty_model.aggregate(view=empty_model.view(), feature="value")

    kind = relationship_classification()
    cycle_model = rk.graph.Model()
    cycle_entities = tuple(
        rk.graph.Entity(entity_id=entity_id) for entity_id in ("a", "b")
    )
    cycle_model.add_entities(cycle_entities)
    cycle_model.add_relationships(
        (
            rk.graph.Relationship("a", "b", kind, relationship_id="a-b"),
            rk.graph.Relationship("b", "a", kind, relationship_id="b-a"),
        )
    )
    with pytest.raises(rk.graph.InvalidAggregationError, match="arborescence"):
        cycle_model.aggregate(view=cycle_model.view(), feature="value")

    parent_model = rk.graph.Model()
    parents = tuple(
        rk.graph.Entity(entity_id=entity_id)
        for entity_id in ("first", "second", "child")
    )
    parent_model.add_entities(parents)
    parent_model.add_relationships(
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
        parent_model.aggregate(view=parent_model.view(), feature="value")


def test_view_must_belong_to_the_aggregating_model():
    first, *_ = tree_model()
    second, *_ = tree_model()

    with pytest.raises(rk.graph.InvalidAggregationError, match="different Model"):
        first.aggregate(view=second.view(), feature="value")


def test_relationship_filtered_overlay_can_be_aggregated():
    model, root, branch, leaf, contains = tree_model()
    root.features["value"] = 1
    branch.features["value"] = 2
    leaf.features["value"] = 3
    services = relationship_classification("relationship.services")
    model.add_relationship(
        rk.graph.Relationship("leaf", "root", services, relationship_id="services")
    )

    with pytest.raises(rk.graph.InvalidAggregationError, match="arborescence"):
        model.aggregate(view=model.view(), feature="value")

    result = model.aggregate(
        view=model.view(relationship_classification=contains),
        feature="value",
    )
    assert result["root"] == 6


def test_stream_sum_can_reduce_flow_and_stream_features():
    model, root, branch, leaf, _ = tree_model()
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

    first = model.aggregate(
        view=model.view(),
        feature="cashflow",
        into="subtotal_cashflow",
        reduce=sum_flux,
    )
    second = model.aggregate(
        view=model.view(),
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
