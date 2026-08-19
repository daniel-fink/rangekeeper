import datetime

import networkx as nx
import pint
import pytest

import rangekeeper as rk


materialization = rk.graph.materialization
units = rk.measure.Index.registry


def materialized_model():
    entity_root = rk.graph.Classification(
        code="entity", name="Entity", scheme="project.entity"
    )
    building_kind = entity_root.define(code="building", name="Building")
    space_kind = entity_root.define(code="space", name="Space")
    office_kind = space_kind.define(code="office", name="Office")
    entity_root.define(code="retail", name="Unused Retail Type")

    uses = rk.graph.Classification(code="use", name="Use", scheme="ABS FCB")
    office_use = uses.define(code="231", name="Offices")
    uses.define(code="233", name="Shops")

    relationship_root = rk.graph.Classification(
        code="relationship",
        name="Relationship",
        scheme="project.relationship",
    )
    contains = relationship_root.define(code="contains", name="Contains")
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
            occupancy={"use": (office_use,)},
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
    model = rk.graph.Model()
    model.add_assembly(property_assembly)
    return model


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


def test_model_snapshot_contains_only_neutral_records_and_stable_references():
    model = materialized_model()

    snapshot = materialization.to_snapshot(model)

    assert snapshot.schema_version == 1
    assert {record.record_type for record in snapshot.records} == {
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


def test_model_snapshot_round_trip_preserves_domain_structure_and_values():
    original = materialized_model()
    snapshot = materialization.to_snapshot(original)

    restored = rk.graph.Model.from_snapshot(snapshot)

    assert restored.validate().is_valid
    assert materialization.to_snapshot(restored) == snapshot
    assert isinstance(restored.entity("property"), rk.graph.Assembly)
    assert isinstance(restored.entity("level"), rk.graph.Assembly)
    assert type(restored.entity("office")) is rk.graph.Entity

    property_assembly = restored.entity("property")
    level = restored.entity("level")
    office = restored.entity("office")
    assert property_assembly.entities == frozenset({level})
    assert property_assembly.relationships == frozenset(
        {restored.relationship("property-level")}
    )
    assert level.entities == frozenset({office})
    assert level.relationships == frozenset({restored.relationship("level-office")})
    assert restored.relationship("level-office").source_id == "level"
    assert restored.relationship("level-office").target_id == "office"

    assert office.classification.code == "office"
    assert office.classification.parent.code == "space"
    assert office.classification.root().find("retail") is not None
    assert office.occupancy["use"][0].scheme == "ABS FCB"
    assert office.occupancy["use"][0].root().find("233") is not None
    assert office.provenance.identifiers == {"object_id": "office-object"}
    assert restored.relationship("level-office").provenance.identifiers == {"row": "12"}
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


def test_model_from_snapshot_uses_the_supplied_unit_registry():
    registry = pint.UnitRegistry()
    registry.define("squaremeter = 1 m**2 = m2 = sqm")
    registry.define("squarefoot = 1 foot**2 = ft2 = sqft")

    restored = rk.graph.Model.from_snapshot(
        materialization.to_snapshot(materialized_model()),
        registry=registry,
    )

    office = restored.entity("office")
    measure = next(iter(office.measures))
    assert measure.units._REGISTRY is registry
    assert office.measures[measure]._REGISTRY is registry
    assert office.features["allowance"]._REGISTRY is registry


def test_view_snapshot_expands_assembly_references_without_networkx_state():
    model = materialized_model()
    root_only = model.view(predicate=lambda entity: entity.entity_id == "property")

    restored = rk.graph.Model.from_snapshot(materialization.to_snapshot(root_only))

    assert {entity.entity_id for entity in restored.entities()} == {
        "property",
        "level",
        "office",
    }
    assert {
        relationship.relationship_id for relationship in restored.relationships()
    } == {
        "property-level",
        "level-office",
    }
    assert restored.validate().is_valid


def test_view_snapshot_of_plain_entity_remains_scoped():
    model = materialized_model()
    office_only = model.view(predicate=lambda entity: entity.entity_id == "office")

    restored = rk.graph.Model.from_snapshot(materialization.to_snapshot(office_only))

    assert tuple(entity.entity_id for entity in restored.entities()) == ("office",)
    assert restored.relationships() == ()
    assert restored.entity("office").classification.root().find("retail") is not None


def test_unsupported_feature_reports_owner_feature_and_type():
    model = materialized_model()
    model.entity("office").features["runtime"] = object()

    with pytest.raises(
        materialization.UnsupportedValueError,
        match=r"entity 'office' feature 'runtime'.*object",
    ):
        materialization.to_snapshot(model)


def test_non_string_feature_mapping_keys_are_rejected_precisely():
    model = materialized_model()
    model.entity("office").features["bad"] = {1: "value"}

    with pytest.raises(
        materialization.UnsupportedValueError,
        match="mapping key type int",
    ):
        materialization.to_snapshot(model)


def test_model_from_snapshot_rejects_dangling_relationship_references():
    snapshot = materialization.to_snapshot(materialized_model())
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
        rk.graph.Model.from_snapshot(malformed)


def test_model_from_snapshot_rejects_invalid_inputs():
    with pytest.raises(TypeError, match="snapshot must be a Snapshot"):
        rk.graph.Model.from_snapshot(object())
    with pytest.raises(materialization.SnapshotError, match="schema version"):
        rk.graph.Model.from_snapshot(
            materialization.Snapshot(schema_version=2, records=())
        )
    with pytest.raises(materialization.SnapshotError, match="unknown record type"):
        rk.graph.Model.from_snapshot(
            materialization.Snapshot(
                schema_version=1,
                records=(
                    materialization.Record(
                        record_type="unknown", identifier="x", values={}
                    ),
                ),
            )
        )
