from dataclasses import replace

import pint
import pytest

from rangekeeper.legacy.graph import Characteristics, Definitions, Entity, Graph, Measurement
from rangekeeper.legacy.graph.adapter import json as adapter
from rangekeeper.legacy.graph.provenance import Claim, Fact, Method, Provenance
from rangekeeper.legacy.graph.reduction import by_measure
from rangekeeper.legacy.measure import AggregationRule, Index, Measure


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


