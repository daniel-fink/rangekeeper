"""Shared schema example exercised through the existing graph architecture.

The builder is a bounded test fixture, not a production interchange adapter.
Schema record validation is exercised by schema/checks/validate.py.
"""

import copy
import hashlib
import json
import math
from pathlib import Path
from uuid import UUID

import pytest

from rangekeeper.graph import (
    Assembly,
    Characteristics,
    Classification,
    Definitions,
    Entity,
    Graph,
    Label,
    Measurement,
    Relationship,
    Taxonomy,
)
from rangekeeper.graph.adapter import json as adapter
from rangekeeper.graph.provenance import (
    Claim,
    ClaimKind,
    Fact,
    Location,
    Method,
    Provenance,
    Reconciliation,
    ReconciliationStatus,
    Source,
)
from rangekeeper.measure import Index, Measure


EXAMPLES = Path(__file__).resolve().parents[2] / "schema/examples"


def load_document(text):
    def unique_keys(pairs):
        record = {}
        for key, value in pairs:
            if key in record:
                raise ValueError(f"duplicate dictionary key: {key}")
            record[key] = value
        return record

    return json.loads(text, object_pairs_hook=unique_keys)


def document():
    return load_document((EXAMPLES / "structural-graph.json").read_text())


def build(doc):
    """Construct canonical runtime objects from this example's record profile."""
    registered = {}

    def register(record, obj):
        key = UUID(record["id"])
        if key in registered:
            raise ValueError("duplicate UUID")
        registered[key] = obj
        return obj

    def unique(values):
        if len(values) != len(set(values)):
            raise ValueError("duplicate membership/reference")
        return values

    taxonomies = []
    for taxonomy in doc["definitions"]["taxonomies"]:
        records = {UUID(item["id"]): item for item in taxonomy["classifications"]}
        if len(records) != len(taxonomy["classifications"]):
            raise ValueError("duplicate Classification UUID")
        local, visiting = {}, set()

        def classification(identifier):
            if identifier in visiting:
                raise ValueError("Classification parent cycle")
            if identifier in local:
                return local[identifier]
            visiting.add(identifier)
            record = records[identifier]
            item = Classification(
                id=identifier,
                code=record["code"],
                name=record["name"],
                parent=(
                    classification(UUID(record["parent"]))
                    if record.get("parent") is not None
                    else None
                ),
            )
            local[identifier] = register(record, item)
            visiting.remove(identifier)
            return item

        for identifier in records:
            classification(identifier)
        taxonomies.append(
            register(
                taxonomy,
                Taxonomy(
                    id=UUID(taxonomy["id"]),
                    code=taxonomy["code"],
                    name=taxonomy["name"],
                    classifications=tuple(local[identifier] for identifier in records),
                ),
            )
        )
    measures = []
    for record in doc["definitions"]["measures"]:
        item = Measure(
            id=UUID(record["id"]),
            code=record["code"],
            name=record["name"],
            units=Index.registry.parse_units(record["units"]),
        )
        measures.append(register(record, item))
    definitions = Definitions(taxonomies=taxonomies, measures=measures)

    def classref(reference):
        return definitions._resolve_classification(UUID(reference))

    def measureref(reference):
        return definitions._resolve_measure(UUID(reference))

    def classrefs(references):
        items = tuple(classref(ref) for ref in references)
        unique([item.id for item in items])
        return items

    def quantity(content, measure):
        if content is None:
            return None
        if not isinstance(content, dict) or set(content) != {"magnitude", "units"}:
            raise ValueError("Quantity requires magnitude and units")
        magnitude = content["magnitude"]
        if type(magnitude) not in (int, float) or not math.isfinite(magnitude):
            raise ValueError("magnitude must be finite numerical content")
        units = content["units"]
        if not isinstance(units, str) or not units.strip():
            raise ValueError("Quantity units must be explicit")
        value = Index.registry.Quantity(magnitude, units)
        measure.validate_quantity(value)
        return value

    def characteristics(record):
        labels, measurements = {}, {}
        for item in record.get("labels", []):
            key = item["key"]
            if not key.strip() or key in labels:
                raise ValueError("invalid local key")
            labels[key] = register(
                item,
                Label(
                    id=UUID(item["id"]),
                    key=key,
                    classifications=classrefs(item.get("classifications", [])),
                ),
            )
        value_keys = set()
        for item in record.get("values", []):
            key = item["key"]
            if not key.strip() or key in value_keys:
                raise ValueError("invalid local key")
            if item["kind"] != "measurement":
                raise ValueError("unsupported Value kind in fixture")
            if "amount" in item:
                raise ValueError("legacy amount payload is unsupported")
            value_keys.add(key)
            measure = measureref(item["measure"])
            if measure.code in measurements:
                raise ValueError(
                    "runtime fixture supports one Measurement per Measure code"
                )
            measurements[measure.code] = register(
                item,
                Measurement(
                    id=UUID(item["id"]),
                    measure=measure,
                    quantity=quantity(item.get("quantity"), measure),
                ),
            )
        return Characteristics(labels=labels, measurements=measurements)

    entities = []
    for group, cls in (("entities", Entity), ("assemblies", Assembly)):
        for record in doc[group]:
            membership = (
                {}
                if cls is Entity
                else {
                    field: frozenset(UUID(x) for x in unique(record.get(slot, [])))
                    for field, slot in (
                        ("entity_ids", "entities"),
                        ("relationship_ids", "relationships"),
                    )
                }
            )
            item = cls(
                id=UUID(record["id"]),
                code=record.get("code"),
                name=record.get("name"),
                classification=(
                    classref(record["classification"])
                    if record.get("classification") is not None
                    else None
                ),
                characteristics=characteristics(record.get("characteristics", {})),
                **membership,
            )
            entities.append(register(record, item))
    relationships = []
    for record in doc["relationships"]:
        relationships.append(
            register(
                record,
                Relationship(
                    id=UUID(record["id"]),
                    source_id=UUID(record["source"]),
                    target_id=UUID(record["target"]),
                    classification=classref(record["classification"]),
                    characteristics=characteristics(record.get("characteristics", {})),
                ),
            )
        )
    provenance = doc["provenance"]
    sources = {}
    for record in provenance["sources"]:
        sources[UUID(record["id"])] = register(
            record,
            Source(
                id=UUID(record["id"]),
                name=record["name"],
                checksum=record["checksum"],
            ),
        )
    records = {UUID(x["id"]): x for x in provenance["claims"]}
    if len(records) != len(provenance["claims"]):
        raise ValueError("duplicate Claim UUID")
    claims, visiting = {}, set()

    def claim(identifier):
        if identifier in visiting:
            raise ValueError("claim dependency cycle")
        if identifier in claims:
            return claims[identifier]
        visiting.add(identifier)
        record = records[identifier]
        content = record["content"]
        if isinstance(content, dict) and set(content) == {"classifications"}:
            content = classrefs(content["classifications"])
        elif isinstance(content, dict):
            if set(content) not in ({"measure"}, {"measure", "quantity"}):
                raise ValueError("unsupported Claim payload")
            content = quantity(content.get("quantity"), measureref(content["measure"]))
        else:
            raise ValueError("unsupported Claim payload in fixture")
        supports = tuple(
            (
                claim(UUID(x))
                if isinstance(x, str)
                else Location(
                    source=sources[UUID(x["source"])],
                    reference=x.get("address", {}),
                )
            )
            for x in record.get("sources", [])
        )
        item = Claim(
            id=identifier,
            value=content,
            kind=ClaimKind(record["kind"]),
            sources=supports,
            method=Method(**record["method"]) if record.get("method") else None,
        )
        claims[identifier] = register(record, item)
        visiting.remove(identifier)
        return item

    for identifier in records:
        claim(identifier)
    facts = []
    for record in provenance["facts"]:
        target = registered[UUID(record["target"])]
        if isinstance(target, Measurement):
            for support in record["claims"]:
                payload = records[UUID(support)]["content"]
                if UUID(payload["measure"]) != target.measure.id:
                    raise ValueError(
                        "Claim Measure UUID must match the target Measurement"
                    )
        r = record.get("reconciliation")
        reconciliation = (
            None
            if r is None
            else Reconciliation(
                selected=claims[UUID(r["selected"])],
                status=ReconciliationStatus(r["status"]),
                method=Method(**r["method"]) if r.get("method") else None,
            )
        )
        facts.append(
            Fact(
                target=target,
                claims=tuple(claims[UUID(x)] for x in record["claims"]),
                reconciliation=reconciliation,
            )
        )
    return Graph(
        definitions=definitions,
        entities=tuple(entities),
        relationships=tuple(relationships),
        provenance=Provenance(facts=tuple(facts)),
    )


def test_shared_example_identity_membership_and_provenance():
    doc = document()
    graph = build(doc)
    first, second = graph.entity("A"), graph.entity("B")
    assert first.measurements["area"].quantity is None
    assert second.measurements["area"].quantity.magnitude == 85.5
    assert len(graph.containing_assemblies(second)) == 2
    assert graph.entities_in("FLOOR")[1] is graph.entities_in("REVIEW")[0]
    assert graph.provenance.fact_for(first.measurements["area"]) is None
    fact = graph.provenance.fact_for(second.measurements["area"])
    assert fact.target is second.measurements["area"]
    assert fact.current_claim.kind is ClaimKind.DERIVED
    assert len(fact.current_claim.sources) == 2
    assert graph.provenance.fact_for(first.labels["use"]).target is first.labels["use"]
    encoded = adapter.dumps(graph)
    restored = adapter.loads(encoded)
    assert adapter.dumps(restored) == encoded
    assert (
        restored.provenance.fact_for(restored.entity("B").measurements["area"]).target
        is restored.entity("B").measurements["area"]
    )
    checksum = hashlib.sha256(
        (EXAMPLES / "structural-evidence.txt").read_bytes()
    ).hexdigest()
    assert checksum == doc["provenance"]["sources"][0]["checksum"]


@pytest.mark.parametrize(
    "case",
    [
        "dangling_endpoint",
        "wrong_kind_endpoint",
        "self_membership",
        "cycle",
        "missing_member",
        "missing_member_endpoint",
        "duplicate_member",
        "duplicate_id",
        "blank_key",
        "duplicate_local_key",
        "wrong_target",
        "dangling_target",
        "duplicate_fact",
        "mismatched_claim",
        "claim_cycle",
        "wrong_source_kind",
        "missing_method",
        "duplicate_label_class",
        "nonfinite_amount",
        "wrong_reconciliation",
        "empty_source",
        "duplicate_entity_code",
        "duplicate_measure_code",
        "blank_taxonomy_code",
        "unknown_classification",
        "unknown_measure",
        "wrong_kind_classification",
        "wrong_kind_measure",
        "parent_cycle",
        "missing_parent",
        "duplicate_definition_id",
        "duplicate_classification_code",
    ],
)
def test_semantic_rejections(case):
    doc = copy.deepcopy(document())
    a, b = doc["entities"]
    assembly, other = doc["assemblies"]
    claims = doc["provenance"]["claims"]
    facts = doc["provenance"]["facts"]
    taxonomy = doc["definitions"]["taxonomies"][0]
    measure = doc["definitions"]["measures"][0]
    unknown = "00000000-0000-0000-0000-000000000000"
    if case == "duplicate_entity_code":
        assembly["code"] = a["code"]
    elif case == "duplicate_measure_code":
        doc["definitions"]["measures"].append({**measure, "id": unknown})
    elif case == "blank_taxonomy_code":
        taxonomy["code"] = " "
    elif case == "unknown_classification":
        a["classification"] = unknown
    elif case == "wrong_kind_classification":
        a["classification"] = measure["id"]
    elif case == "unknown_measure":
        a["characteristics"]["values"][0]["measure"] = unknown
    elif case == "wrong_kind_measure":
        a["characteristics"]["values"][0]["measure"] = taxonomy["classifications"][0][
            "id"
        ]
    elif case == "parent_cycle":
        taxonomy["classifications"][0]["parent"] = taxonomy["classifications"][1]["id"]
    elif case == "missing_parent":
        taxonomy["classifications"][1]["parent"] = unknown
    elif case == "duplicate_definition_id":
        taxonomy["classifications"][1]["id"] = taxonomy["classifications"][0]["id"]
    elif case == "duplicate_classification_code":
        taxonomy["classifications"][1]["code"] = taxonomy["classifications"][0]["code"]
    elif case == "dangling_endpoint":
        doc["relationships"][0]["source"] = unknown
    elif case == "wrong_kind_endpoint":
        doc["relationships"][0]["source"] = b["characteristics"]["values"][0]["id"]
    elif case == "self_membership":
        assembly["entities"].append(assembly["id"])
    elif case == "cycle":
        assembly["entities"].append(other["id"])
        other["entities"].append(assembly["id"])
    elif case == "missing_member":
        assembly["entities"].append(unknown)
    elif case == "missing_member_endpoint":
        assembly["entities"].remove(a["id"])
    elif case == "duplicate_member":
        assembly["entities"].append(a["id"])
    elif case == "duplicate_id":
        b["id"] = a["id"]
    elif case == "blank_key":
        a["characteristics"]["values"][0]["key"] = " "
    elif case == "duplicate_local_key":
        a["characteristics"]["labels"].append(
            {**a["characteristics"]["labels"][0], "id": unknown}
        )
    elif case == "wrong_target":
        facts[0]["target"] = measure["id"]
    elif case == "dangling_target":
        facts[0]["target"] = unknown
    elif case == "duplicate_fact":
        facts.append(copy.deepcopy(facts[0]))
    elif case == "mismatched_claim":
        claims[2]["content"]["quantity"]["magnitude"] = 99
    elif case == "claim_cycle":
        claims[2]["sources"].append(claims[2]["id"])
    elif case == "wrong_source_kind":
        claims[2]["sources"] = claims[0]["sources"]
    elif case == "empty_source":
        claims[0]["sources"] = []
    elif case == "missing_method":
        claims[2].pop("method")
    elif case == "duplicate_label_class":
        a["characteristics"]["labels"][0]["classifications"] *= 2
    elif case == "nonfinite_amount":
        b["characteristics"]["values"][0]["quantity"]["magnitude"] = float("nan")
    elif case == "wrong_reconciliation":
        facts[0]["reconciliation"] = {
            "selected": claims[0]["id"],
            "status": "confirmed",
        }
    with pytest.raises((ValueError, TypeError, KeyError)):
        build(doc)


def test_duplicate_record_fields_rejected_before_overwrite():
    with pytest.raises(ValueError, match="duplicate dictionary key"):
        load_document('{"code":"a","code":"b"}')


@pytest.mark.parametrize(
    "reference",
    ["apartment", "example.apartment", {"taxonomy": "example", "code": "apartment"}],
)
@pytest.mark.parametrize("site", ["entity", "label", "measure", "parent", "claim"])
def test_serialized_references_require_uuids(reference, site):
    doc = document()
    entity = doc["entities"][0]
    if site == "entity":
        entity["classification"] = reference
    elif site == "label":
        entity["characteristics"]["labels"][0]["classifications"] = [reference]
    elif site == "measure":
        entity["characteristics"]["values"][0]["measure"] = reference
    elif site == "parent":
        doc["definitions"]["taxonomies"][0]["classifications"][1]["parent"] = reference
    elif site == "claim":
        doc["provenance"]["claims"][0]["content"]["measure"] = reference
    with pytest.raises((ValueError, TypeError, AttributeError)):
        build(doc)


def test_definition_renames_preserve_uuid_references_and_provenance():
    doc = document()
    original = build(doc)
    taxonomy = doc["definitions"]["taxonomies"][0]
    taxonomy["code"] = "renamed.taxonomy"
    for record in taxonomy["classifications"]:
        record["code"] = "renamed." + record["code"]
        record["name"] = "Renamed " + record["name"]
    doc["definitions"]["measures"][0]["code"] = "renamed.area"
    doc["entities"][0]["characteristics"]["labels"][0]["key"] = "renamed_use"
    renamed = build(doc)
    assert (
        original.entity("A").classification.id == renamed.entity("A").classification.id
    )
    area = renamed.entity("B").measurements["renamed.area"]
    assert area.id == original.entity("B").measurements["area"].id
    assert renamed.provenance.fact_for(area).target is area
    label = renamed.entity("A").labels["renamed_use"]
    assert renamed.provenance.fact_for(label).target is label


def test_parent_references_do_not_depend_on_list_order():
    doc = document()
    doc["definitions"]["taxonomies"][0]["classifications"].reverse()
    graph = build(doc)
    assert graph.entity("A").classification.parent.code == "object"


def test_claim_measure_identity_cannot_be_replaced_by_matching_units():
    doc = document()
    other_measure = {
        **doc["definitions"]["measures"][0],
        "id": "00000000-0000-0000-0000-000000000001",
        "code": "other_area",
    }
    doc["definitions"]["measures"].append(other_measure)
    doc["provenance"]["claims"][2]["content"]["measure"] = other_measure["id"]
    with pytest.raises(ValueError, match="Claim Measure UUID must match"):
        build(doc)


def test_quantity_units_can_differ_from_measure_canonical_units():
    doc = document()
    doc["entities"][1]["characteristics"]["values"][0]["quantity"] = {
        "magnitude": 855000,
        "units": "cm^2",
    }
    graph = build(doc)
    reading = graph.entity("B").measurements["area"]
    assert reading.quantity.magnitude == 855000
    assert reading.quantity.units == Index.registry.centimeter**2
    assert reading.quantity.to(reading.measure.units).magnitude == pytest.approx(85.5)
    fact = graph.provenance.fact_for(reading)
    assert fact.current_claim.value == reading.quantity
    restored = adapter.loads(adapter.dumps(graph))
    assert restored.entity("B").measurements["area"].quantity == reading.quantity


@pytest.mark.parametrize("site", ["value", "claim"])
def test_quantity_incompatible_units_rejected(site):
    doc = document()
    content = (
        doc["entities"][1]["characteristics"]["values"][0]
        if site == "value"
        else doc["provenance"]["claims"][2]["content"]
    )
    content["quantity"]["units"] = "m"
    with pytest.raises(TypeError, match="Cannot convert"):
        build(doc)


@pytest.mark.parametrize("content", [None, {"magnitude": 0, "units": "m^2"}])
def test_quantity_unresolved_and_zero_remain_distinct(content):
    doc = document()
    doc["entities"][0]["characteristics"]["values"][0]["quantity"] = content
    reading = build(doc).entity("A").measurements["area"]
    if content is None:
        assert reading.quantity is None
    else:
        assert reading.quantity is not None
        assert reading.quantity.magnitude == 0


def test_parent_must_belong_to_the_same_taxonomy():
    doc = document()
    other_parent = {
        "id": "00000000-0000-0000-0000-000000000001",
        "code": "other_parent",
        "name": "Other parent",
    }
    doc["definitions"]["taxonomies"].append(
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "code": "other",
            "name": "Other",
            "classifications": [other_parent],
        }
    )
    doc["definitions"]["taxonomies"][0]["classifications"][1]["parent"] = other_parent[
        "id"
    ]
    with pytest.raises(KeyError):
        build(doc)
