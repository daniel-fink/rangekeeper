import json
from datetime import datetime, time, timedelta
from types import MappingProxyType
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from rangekeeper.graph import (
    Assembly,
    Characteristics,
    Classification,
    Definitions,
    Entity,
    Feature,
    Graph,
    Measurement,
    Relationship,
    Taxonomy,
)
from rangekeeper.graph.adapter import json as adapter
from rangekeeper.adapters.errors import AdapterEncodingError
from rangekeeper.graph.provenance import (
    Claim,
    Fact,
    Location,
    Method,
    Provenance,
    Reconciliation,
    ReconciliationStatus,
    Source,
)
from rangekeeper.graph.revision import Diff
from rangekeeper.measure import Index, Measure, QuantityKind


def example():
    classification = Classification(code="equipment", name="Equipment")
    measure = Measure(
        code="length",
        name="Length",
        units=Index.registry.meter,
        quantity_kind=QuantityKind.LENGTH,
    )
    reading = Measurement(measure=measure, quantity=0.0 * Index.registry.meter)
    feature = Feature(
        name="payload",
        value={
            "list": [False, 1, 1.0, uuid4()],
            "tuple": (None, timedelta(days=2, microseconds=3)),
            "frozen": frozenset({"x", "y"}),
            "mapping": MappingProxyType({"time": time(12, 30)}),
            "date": datetime(2020, 7, 1, 12, tzinfo=ZoneInfo("Australia/Sydney")),
        },
    )
    child = Entity(
        code="pump",
        classification=classification,
        characteristics=Characteristics(
            measurements={"length": reading}, features={"payload": feature}
        ),
    )
    parent_id, edge_id = uuid4(), uuid4()
    parent = Assembly(
        id=parent_id,
        code="system",
        classification=classification,
        entity_ids=frozenset({child.id}),
        relationship_ids=frozenset({edge_id}),
    )
    edge = Relationship(
        id=edge_id,
        source_id=parent.id,
        target_id=child.id,
        classification=classification,
    )
    source = Source(name="measurement", checksum="abc")
    first = Claim.sourced(
        reading.quantity, at=Location(source=source, reference={"cell": "A1"})
    )
    second = Claim.derived(
        1 * Index.registry.meter,
        from_claims=(first,),
        method=Method(code="adjust", version="1"),
    )
    fact = Fact(
        target=reading,
        claims=(first, second),
        reconciliation=Reconciliation(
            selected=first, status=ReconciliationStatus.CONFIRMED
        ),
    )
    return Graph(
        definitions=Definitions(
            taxonomies=(
                Taxonomy(code="types", name="Types", classifications=(classification,)),
            ),
            measures=(measure,),
        ),
        entities=(parent, child),
        relationships=(edge,),
        provenance=Provenance(facts=(fact,)),
    )


def test_roundtrip_preserves_canonical_references_and_types(tmp_path):
    original = example()
    encoded = adapter.dumps(original)
    graph = adapter.loads(encoded)
    assert not Diff.between(original, graph).changed
    assert encoded == adapter.dumps(graph)
    fact = graph.provenance.facts[0]
    assert fact.target is graph.entities[1].measurements["length"]
    assert fact.claims[1].sources[0] is fact.claims[0]
    assert fact.reconciliation.selected is fact.claims[0]
    assert graph.entities[0].classification is graph.entities[1].classification
    assert (
        graph.entities[1].measurements["length"].measure
        is graph.definitions.measures["length"]
    )
    path = adapter.write(graph, tmp_path / "graph.json")
    assert not Diff.between(graph, adapter.read(path)).changed


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x.update(version=2),
        lambda x: x["objects"].append(x["objects"][0]),
        lambda x: x["objects"].pop(),
        lambda x: x["root"].update(object="Executable"),
        lambda x: x["root"]["fields"].update(invented=True),
    ],
)
def test_invalid_documents_fail(change):
    doc = json.loads(adapter.dumps(example()))
    change(doc)
    with pytest.raises(AdapterEncodingError):
        adapter.loads(json.dumps(doc))


def test_unknown_payload_and_cycles_do_not_overwrite(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text("previous")
    for value in (object(), float("nan")):
        graph = Graph(
            entities=(
                Entity(
                    characteristics=Characteristics(
                        features={"bad": Feature(name="bad", value=value)}
                    )
                ),
            )
        )
        with pytest.raises(AdapterEncodingError):
            adapter.write(graph, path)
        assert path.read_text() == "previous"
    data = []
    data.append(data)
    graph = Graph(
        entities=(
            Entity(
                characteristics=Characteristics(
                    features={"bad": Feature(name="bad", value=data)}
                )
            ),
        )
    )
    with pytest.raises(AdapterEncodingError, match="Cyclic"):
        adapter.dumps(graph)


def test_duplicate_json_keys_and_unregistered_types():
    with pytest.raises(AdapterEncodingError):
        adapter.loads('{"format":"rk.graph","format":"other"}')
    with pytest.raises(TypeError):
        adapter.dumps({})


def test_named_timezone_ambiguous_fold():
    value = datetime(2020, 11, 1, 1, 30, fold=1, tzinfo=ZoneInfo("America/New_York"))
    graph = Graph(
        entities=(
            Entity(
                characteristics=Characteristics(
                    features={"time": Feature(name="time", value=value)}
                )
            ),
        )
    )
    restored = adapter.loads(adapter.dumps(graph)).entities[0].features["time"].value
    assert restored.fold == 1
    assert restored.tzinfo.key == value.tzinfo.key
    assert restored.isoformat() == value.isoformat()


@pytest.mark.parametrize(
    "payload",
    [
        {"int": "01"},
        {"float": "nan"},
        {"float": "1.0"},
        {"enum": ["ClaimKind", "sourced", "extra"]},
        {"datetime": ["2020-01-01T00:00:00", True, None]},
        {"timedelta": [0, 86400, 0]},
        {"quantity": [{"int": "1"}, "m", "extra"]},
        {"frozenset": [{"int": "1"}, {"int": "1"}]},
        {"dict": [[{"int": "1"}]]},
        {"uuid": 12},
    ],
)
def test_malformed_payload_tags_fail(payload):
    graph = Graph(
        entities=(
            Entity(
                characteristics=Characteristics(
                    features={"value": Feature(name="value", value=1)}
                )
            ),
        )
    )
    document = json.loads(adapter.dumps(graph))
    feature = next(r for r in document["objects"] if r["type"] == "Feature")
    feature["fields"]["value"] = payload
    with pytest.raises(AdapterEncodingError):
        adapter.loads(json.dumps(document))


def test_conflicting_facts_and_all_temporal_scalars():
    from datetime import date, timezone

    value = (
        date(2024, 2, 29),
        datetime(2020, 1, 1),  # noqa: DTZ001 - naive temporal values are a supported payload
        time(12, 30, tzinfo=timezone.utc),
        -0.0,
        False,
        1,
        1.0,
    )
    feature = Feature(name="typed", value=value)
    entity = Entity(characteristics=Characteristics(features={"typed": feature}))
    first = Claim.asserted(value, method=Method(code="survey", version="1"))
    second = Claim.asserted(None, method=Method(code="survey", version="2"))
    graph = Graph(
        entities=(entity,),
        provenance=Provenance(
            facts=(
                Fact(
                    target=feature,
                    claims=(first, second),
                    reconciliation=Reconciliation(
                        selected=first, status=ReconciliationStatus.PROVISIONAL
                    ),
                ),
            )
        ),
    )
    restored = adapter.loads(adapter.dumps(graph))
    assert not Diff.between(graph, restored).changed
    actual = restored.entities[0].features["typed"].value
    assert [type(v) for v in actual] == [type(v) for v in value]
    assert actual[3].hex() == "-0x0.0p+0"
