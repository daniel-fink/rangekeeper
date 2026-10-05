from dataclasses import replace

import pint
import pytest

from rangekeeper.graph import Characteristics, Definitions, Entity, Graph, Measurement
from rangekeeper.graph.adapter import json as adapter
from rangekeeper.graph.provenance import Claim, Fact, Method, Provenance
from rangekeeper.graph.legacy.reduction import by_measure
from rangekeeper.workflow._operands import model_operand, operand
from rangekeeper.measure import AggregationRule, Index, Measure


@pytest.fixture
def unresolved():
    measure = Measure(
        code="area",
        name="Area",
        units=Index.registry.meter**2,
        aggregation=AggregationRule.SUM,
    )
    reading = Measurement(measure=measure)
    entity = Entity(
        code="A", characteristics=Characteristics(measurements={"area": reading})
    )
    graph = Graph(definitions=Definitions(measures=(measure,)), entities=(entity,))
    return graph, entity, reading


def test_unresolved_and_resolved_snapshots_preserve_identity_and_provenance(unresolved):
    original, entity, reading = unresolved
    resolved = replace(reading, quantity=85.5 * reading.measure.units)
    updated = replace(
        entity, characteristics=Characteristics(measurements={"area": resolved})
    )
    source = Claim.asserted(85.5 * reading.measure.units, method=Method(code="input"))
    result = Claim.derived(
        resolved.quantity, from_claims=(source,), method=Method(code="calculation")
    )
    output = replace(
        original,
        entities=(updated,),
        provenance=Provenance(facts=(Fact(target=resolved, claims=(result,)),)),
    )
    assert reading.quantity is None
    assert resolved.id == reading.id
    assert output.provenance.fact_for(resolved).current_claim is result
    assert original.provenance.fact_for(reading) is None
    for graph in (original, output):
        restored = adapter.loads(adapter.dumps(graph))
        target = restored.entities[0].measurements["area"]
        assert target.id == reading.id
        assert target.quantity == graph.entities[0].measurements["area"].quantity
        if graph is output:
            assert restored.provenance.fact_for(target).target is target


def test_zero_is_resolved_and_validation_still_applies(unresolved):
    _, _, reading = unresolved
    zero = replace(reading, quantity=0 * reading.measure.units)
    assert zero.quantity is not None
    assert zero.quantity.magnitude == 0
    with pytest.raises(TypeError):
        replace(reading, quantity=0)
    with pytest.raises(pint.DimensionalityError):
        replace(reading, quantity=1 * Index.registry.meter)


def test_unresolved_reduction_reports_missing_not_zero(unresolved):
    graph, entity, reading = unresolved
    result = graph.view().aggregate(
        by_measure(reading.measure, require_measurement=True)
    )
    assert result[entity] is None
    assert result.coverage(entity).missing == (entity.id,)
    assert result.known_subtotal(entity) is None


def test_workflow_operands_preserve_unresolved_and_zero():
    from uuid import uuid4
    from rangekeeper.model import (
        Model,
        Metadata,
        System,
        Definitions,
        Measure,
        Value,
        Entity,
        Characteristics,
    )

    measure = Measure(id=uuid4(), code="area", name="Area", units="meter**2")
    reading = Value(id=uuid4(), key="net", kind="measurement", measure=measure.id)
    entity = Entity(
        id=uuid4(), code="A", characteristics=Characteristics(values=(reading,))
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.4.0"),
        definitions=Definitions(measures=(measure,)),
        system=System(entities=(entity,)),
    )
    by_key = {("space", "A"): entity}
    single = {
        "kind": "model_value",
        "identity_kind": "space",
        "key": {"value": "A"},
        "value_key": "net",
        "units": "meter**2",
    }
    result = operand(single, None, None, model, by_key, {})
    assert result.value is None and result.targets == (str(reading.id),)
    total = model_operand(
        {"kind": "model_total", "value_key": "net", "units": "meter**2"},
        None,
        None,
        model,
        by_key,
        {},
    )
    assert (
        total.value is None and total.known_subtotal is None and total.missing == ("A",)
    )
    match_zero = {"kind": "model_count", "value_key": "net", "binding": {"value": 0}}
    assert model_operand(match_zero, None, None, model, by_key, {}).value == 0
    data = model.to_data()
    data["metadata"]["id"] = str(uuid4())
    data["system"]["entities"][0]["characteristics"]["values"][0]["quantity"] = {
        "magnitude": 0,
        "units": "meter**2",
    }
    output = Model.from_data(data)
    assert model_operand(match_zero, None, None, output, {}, {}).value == 1
    assert (
        operand(
            single, None, None, output, {("space", "A"): output.entity(entity.id)}, {}
        ).value
        == 0
    )

    # A retained business-key index must not read quantities from an older revision.
    assert operand(single, None, None, output, by_key, {}).value == 0
