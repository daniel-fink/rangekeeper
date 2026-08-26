import datetime

import networkx as nx
import pint
import pytest

import rangekeeper as rk
from rangekeeper.graph.materialization import value as encoded_value


materialization = rk.graph.materialization
units = rk.measure.Index.registry


def materialized_graph():
    entity_root = rk.graph.Taxonomy(code="project.entity", name="Entity Types").define(
        code="entity", name="Entity"
    )
    building_kind = entity_root.define(code="building", name="Building")
    space_kind = entity_root.define(code="space", name="Space")
    office_kind = space_kind.define(code="office", name="Office")
    entity_root.define(code="retail", name="Unused Retail Type")

    uses = rk.graph.Taxonomy(code="ABS FCB", name="Building Uses").define(
        code="use", name="Use"
    )
    office_use = uses.define(code="231", name="Offices")
    uses.define(code="233", name="Shops")

    relationship_root = rk.graph.Taxonomy(
        code="project.relationship", name="Relationship Types"
    ).define(code="relationship", name="Relationship")
    contains = relationship_root.define(code="contains", name="Contains")
    relationship_root.define(code="linked-to", name="Linked To")
    relationship_root.define(code="services", name="Services")

    area = rk.measure.Measure(
        code="project.area",
        name="Area",
        units=units.sqm,
        definition="Gross floor area",
        tags={"physical", "reporting"},
    )
    office = rk.graph.Entity(
        entity_id="office",
        name="Office",
        classification=office_kind,
        characteristics=rk.graph.Characteristics(
            labels={"use": (office_use,)},
            measures={area: 10_000 * units.sqft},
            features={
                "active": True,
                "commissioned": datetime.date(2030, 1, 31),
                "events": [{"name": "Open", "year": 2030}],
                "parameters": ("base", 1.5),
                "allowance": 5 * units.percent,
            },
        ),
        provenance=rk.graph.Provenance(
            source="speckle", identifiers={"object_id": "office-object"}
        ),
    )
    level = rk.graph.Assembly(
        entity_id="level",
        name="Level 1",
        classification=building_kind,
        characteristics=rk.graph.Characteristics(
            measures={area: 1_000 * units.sqm},
            features={"stage": "existing"},
        ),
        provenance=rk.graph.Provenance(
            source="survey", identifiers={"drawing": "A-101"}
        ),
        entities=(office,),
    )
    level_contains_office = rk.graph.Relationship(
        "level",
        "office",
        contains,
        relationship_id="level-office",
        characteristics=rk.graph.Characteristics(features={"confidence": 0.9}),
        provenance=rk.graph.Provenance(source="survey", identifiers={"row": "12"}),
    )
    level._replace_contents(entities=(office,), relationships=(level_contains_office,))
    property_contains_level = rk.graph.Relationship(
        "property",
        "level",
        contains,
        relationship_id="property-level",
    )
    property_assembly = rk.graph.Assembly(
        entity_id="property",
        name="Property",
        classification=building_kind,
        entities=(level,),
        relationships=(property_contains_level,),
    )
    graph = rk.graph.Graph()
    graph.assemblies.add(property_assembly)
    return graph


def test_record_and_snapshot_are_deeply_read_only():
    record = materialization.Record(
        record_type="entity",
        identifier="entity",
        values={"nested": {"items": [1, 2]}},
    )
    snapshot = materialization.Snapshot(schema_version=1, records=[record])

    assert isinstance(snapshot.records, tuple)
    assert record.values["nested"]["items"] == (1, 2)
    with pytest.raises(TypeError):
        record.values["changed"] = True
    with pytest.raises(TypeError):
        record.values["nested"]["changed"] = True


def test_graph_snapshot_contains_only_neutral_records_and_stable_references():
    graph = materialized_graph()

    snapshot = materialization.to_snapshot(graph)

    assert snapshot.schema_version == 2
    assert {record.record_type for record in snapshot.records} == {
        "taxonomy",
        "classification",
        "entity",
        "assembly",
        "relationship",
    }
    property_record = next(
        record for record in snapshot.records if record.identifier == "property"
    )
    assert property_record.record_type == "assembly"
    assert property_record.values["entity_ids"] == ("level",)
    assert property_record.values["relationship_ids"] == ("property-level",)
    office_record = next(
        record for record in snapshot.records if record.identifier == "office"
    )
    encoded_label = office_record.values["characteristics"]["labels"][0]
    assert encoded_label["key"] == "use"
    assert "facet" not in encoded_label
    taxonomy_record = next(
        record for record in snapshot.records if record.identifier == "ABS FCB"
    )
    assert taxonomy_record.record_type == "taxonomy"
    assert taxonomy_record.values["name"] == "Building Uses"
    office_use_record = next(
        record
        for record in snapshot.records
        if record.record_type == "classification" and record.values["code"] == "231"
    )
    assert office_use_record.values["taxonomy"] == "ABS FCB"
    assert office_use_record.values["parent_code"] == "use"

    def values(value):
        if isinstance(value, dict) or hasattr(value, "items"):
            for item in value.values():
                yield from values(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from values(item)
        else:
            yield value

    assert not any(
        isinstance(value, (rk.graph.Entity, rk.graph.Relationship, nx.Graph))
        for record in snapshot.records
        for value in values(record.values)
    )


def test_snapshot_encoding_canonicalizes_nested_mapping_order():
    left = rk.graph.Graph()
    left.entities.add(
        rk.graph.Entity(
            entity_id="entity",
            characteristics=rk.graph.Characteristics(
                features={"mapping": {"a": 1, "b": 2}}
            ),
        )
    )
    right = rk.graph.Graph()
    right.entities.add(
        rk.graph.Entity(
            entity_id="entity",
            characteristics=rk.graph.Characteristics(
                features={"mapping": {"b": 2, "a": 1}}
            ),
        )
    )

    assert materialization.to_snapshot(left) == materialization.to_snapshot(right)


def test_graph_snapshot_round_trip_preserves_domain_structure_and_values():
    original = materialized_graph()
    snapshot = materialization.to_snapshot(original)

    restored = rk.graph.Graph.from_snapshot(snapshot)

    assert restored.validate().is_valid
    assert materialization.to_snapshot(restored) == snapshot
    assert isinstance(restored.entities["property"], rk.graph.Assembly)
    assert isinstance(restored.entities["level"], rk.graph.Assembly)
    assert type(restored.entities["office"]) is rk.graph.Entity

    property_assembly = restored.entities["property"]
    level = restored.entities["level"]
    office = restored.entities["office"]
    assert property_assembly.entities == frozenset({level})
    assert property_assembly.relationships == frozenset(
        {restored.relationships["property-level"]}
    )
    assert level.entities == frozenset({office})
    assert level.relationships == frozenset({restored.relationships["level-office"]})
    assert restored.relationships["level-office"].source_id == "level"
    assert restored.relationships["level-office"].target_id == "office"

    assert office.classification.code == "office"
    assert office.classification.taxonomy.code == "project.entity"
    assert office.classification.taxonomy.is_frozen
    assert office.classification.parent.code == "space"
    assert office.classification.root().find("retail") is not None
    assert office.labels["use"][0].taxonomy.code == "ABS FCB"
    assert office.labels["use"][0].root().find("233") is not None
    assert office.provenance.identifiers == {"object_id": "office-object"}
    assert restored.relationships["level-office"].provenance.identifiers == {
        "row": "12"
    }
    assert office.features["commissioned"] == datetime.date(2030, 1, 31)
    assert office.features["events"] == [{"name": "Open", "year": 2030}]
    assert office.features["parameters"] == ("base", 1.5)
    assert office.features["allowance"] == 5 * units.percent

    office_measure = next(iter(office.measures))
    level_measure = next(iter(level.measures))
    assert office_measure is level_measure
    assert office_measure.to_record() == {
        "code": "project.area",
        "name": "Area",
        "units": "squaremeter",
        "definition": "Gross floor area",
        "tags": ["physical", "reporting"],
    }
    assert office.measures[office_measure].units == units.sqft
    assert office.measures[office_measure].magnitude == 10_000


def test_graph_from_snapshot_uses_the_supplied_unit_registry():
    registry = pint.UnitRegistry()
    registry.define("squaremeter = 1 m**2 = m2 = sqm")
    registry.define("squarefoot = 1 foot**2 = ft2 = sqft")

    restored = rk.graph.Graph.from_snapshot(
        materialization.to_snapshot(materialized_graph()),
        registry=registry,
    )

    office = restored.entities["office"]
    measure = next(iter(office.measures))
    assert measure.units._REGISTRY is registry
    assert office.measures[measure]._REGISTRY is registry
    assert office.features["allowance"]._REGISTRY is registry


def test_graph_snapshot_preserves_an_explicitly_registered_unused_taxonomy():
    taxonomy = rk.graph.Taxonomy(code="uses", name="Uses")
    root = taxonomy.define(code="use", name="Use")
    root.define(code="office", name="Office")
    graph = rk.graph.Graph()
    graph.taxonomies.add(taxonomy)

    restored = rk.graph.Graph.from_snapshot(materialization.to_snapshot(graph))

    assert restored.taxonomies["uses"].classification("office").name == "Office"
    assert restored.taxonomies["uses"].is_frozen


def test_view_snapshot_expands_assembly_references_without_networkx_state():
    graph = materialized_graph()
    root_only = rk.graph.View(
        graph, predicate=lambda entity: entity.entity_id == "property"
    )

    restored = rk.graph.Graph.from_snapshot(materialization.to_snapshot(root_only))

    assert {entity.entity_id for entity in restored.entities.all()} == {
        "property",
        "level",
        "office",
    }
    assert {
        relationship.relationship_id for relationship in restored.relationships.all()
    } == {
        "property-level",
        "level-office",
    }
    assert restored.validate().is_valid


def test_relationship_selected_view_expands_an_assembly_endpoint_to_its_closure():
    graph = materialized_graph()
    linked_to = next(
        taxonomy
        for taxonomy in graph.taxonomies.all()
        if taxonomy.code == "project.relationship"
    ).classification("linked-to")
    external = rk.graph.Entity(entity_id="external")
    graph.entities.add(external)
    graph.relationships.connect(
        external,
        "property",
        linked_to,
        relationship_id="external-property",
    )
    view = rk.graph.View(graph, relationship_classification=linked_to)

    restored = rk.graph.Graph.from_snapshot(materialization.to_snapshot(view))

    assert {entity.entity_id for entity in restored.entities.all()} == {
        "external",
        "property",
        "level",
        "office",
    }
    assert {
        relationship.relationship_id for relationship in restored.relationships.all()
    } == {
        "external-property",
        "property-level",
        "level-office",
    }


def test_view_snapshot_of_plain_entity_remains_scoped():
    graph = materialized_graph()
    office_only = rk.graph.View(
        graph, predicate=lambda entity: entity.entity_id == "office"
    )

    restored = rk.graph.Graph.from_snapshot(materialization.to_snapshot(office_only))

    assert tuple(entity.entity_id for entity in restored.entities.all()) == ("office",)
    assert restored.relationships.all() == ()
    assert restored.entities["office"].classification.root().find("retail") is not None


def test_unsupported_feature_reports_owner_feature_and_type():
    graph = materialized_graph()
    graph.entities["office"].features["runtime"] = object()

    with pytest.raises(
        materialization.UnsupportedValueError,
        match=r"entity 'office' feature 'runtime'.*object",
    ):
        materialization.to_snapshot(graph)


def test_non_string_feature_mapping_keys_are_rejected_precisely():
    graph = materialized_graph()
    graph.entities["office"].features["bad"] = {1: "value"}

    with pytest.raises(
        materialization.UnsupportedValueError,
        match="mapping key type int",
    ):
        materialization.to_snapshot(graph)


def test_graph_from_snapshot_rejects_dangling_relationship_references():
    snapshot = materialization.to_snapshot(materialized_graph())
    records = []
    for record in snapshot.records:
        if record.identifier == "level-office":
            values = dict(record.values)
            values["target_id"] = "missing"
            record = materialization.Record(
                record_type=record.record_type,
                identifier=record.identifier,
                values=values,
            )
        records.append(record)
    malformed = materialization.Snapshot(
        schema_version=snapshot.schema_version,
        records=records,
    )

    with pytest.raises(materialization.SnapshotError, match="missing Entity"):
        rk.graph.Graph.from_snapshot(malformed)


def test_graph_from_snapshot_wraps_invalid_measure_units():
    snapshot = materialization.to_snapshot(materialized_graph())
    records = []
    for record in snapshot.records:
        if record.identifier == "office":
            values = dict(record.values)
            characteristics = dict(values["characteristics"])
            measures = list(characteristics["measures"])
            measure = dict(measures[0])
            definition = dict(measure["measure"])
            definition["items"] = tuple(
                (key, "not_a_unit" if key == "units" else value)
                for key, value in definition["items"]
            )
            measure["measure"] = definition
            measures[0] = measure
            characteristics["measures"] = tuple(measures)
            values["characteristics"] = characteristics
            record = materialization.Record(
                record_type=record.record_type,
                identifier=record.identifier,
                values=values,
            )
        records.append(record)
    malformed = materialization.Snapshot(
        schema_version=snapshot.schema_version,
        records=records,
    )

    with pytest.raises(materialization.SnapshotError, match="Measure is invalid"):
        rk.graph.Graph.from_snapshot(malformed)


def test_graph_from_snapshot_rejects_missing_taxonomy_reference():
    snapshot = materialization.to_snapshot(materialized_graph())
    records = []
    changed = False
    for record in snapshot.records:
        if record.record_type == "classification" and not changed:
            values = dict(record.values)
            values["taxonomy"] = "missing"
            record = materialization.Record(
                record_type=record.record_type,
                identifier=record.identifier,
                values=values,
            )
            changed = True
        records.append(record)

    malformed = materialization.Snapshot(
        schema_version=snapshot.schema_version,
        records=records,
    )

    with pytest.raises(materialization.SnapshotError, match="missing Taxonomy"):
        rk.graph.Graph.from_snapshot(malformed)


def test_graph_from_snapshot_rejects_taxonomy_cycle():
    snapshot = materialization.to_snapshot(materialized_graph())
    records = []
    for record in snapshot.records:
        if (
            record.record_type == "classification"
            and record.values["taxonomy"] == "project.entity"
            and record.values["code"] == "entity"
        ):
            values = dict(record.values)
            values["parent_code"] = "office"
            record = materialization.Record(
                record_type=record.record_type,
                identifier=record.identifier,
                values=values,
            )
        records.append(record)

    malformed = materialization.Snapshot(
        schema_version=snapshot.schema_version,
        records=records,
    )

    with pytest.raises(materialization.SnapshotError, match="cycle"):
        rk.graph.Graph.from_snapshot(malformed)


def test_graph_from_snapshot_rejects_invalid_inputs():
    with pytest.raises(TypeError, match="schema_version must be an integer"):
        materialization.Snapshot(schema_version=True, records=())
    with pytest.raises(TypeError, match="snapshot must be a Snapshot"):
        rk.graph.Graph.from_snapshot(object())
    with pytest.raises(materialization.SnapshotError, match="schema version"):
        rk.graph.Graph.from_snapshot(
            materialization.Snapshot(schema_version=1, records=())
        )
    with pytest.raises(materialization.SnapshotError, match="unknown record type"):
        rk.graph.Graph.from_snapshot(
            materialization.Snapshot(
                schema_version=2,
                records=(
                    materialization.Record(
                        record_type="unknown", identifier="x", values={}
                    ),
                ),
            )
        )


def test_encoded_quantity_wraps_invalid_units_as_snapshot_error():
    with pytest.raises(materialization.SnapshotError, match="quantity units"):
        encoded_value.decode(
            {
                "__rangekeeper_type__": "quantity",
                "magnitude": 1,
                "units": "not_a_unit",
            },
            registry=pint.UnitRegistry(),
            path="feature",
        )
