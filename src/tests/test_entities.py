import pytest

import rangekeeper as rk


def classification(code="building"):
    return rk.graph.Classification(code=code, name=code.title())


def relationship_classification():
    return rk.graph.Classification(code="relationship.contains", name="Contains")


def test_entity_is_a_plain_public_domain_class():
    entity = rk.graph.Entity(name="Building", classification=classification())

    assert rk.graph.entity.Entity is rk.graph.Entity
    assert entity.entity_id
    assert entity.name == "Building"
    assert entity.classification.code == "building"
    assert not hasattr(entity, "entityId")


def test_entity_id_is_validated_and_immutable():
    entity = rk.graph.Entity(entity_id="entity-1")

    assert entity.entity_id == "entity-1"
    with pytest.raises(AttributeError):
        entity.entity_id = "entity-2"
    with pytest.raises(TypeError, match="entity_id"):
        rk.graph.Entity(entity_id=1)
    with pytest.raises(ValueError, match="entity_id"):
        rk.graph.Entity(entity_id=" ")


def test_entity_identity_equality_hashing_and_unrelated_comparison():
    first = rk.graph.Entity(entity_id="same", name="First")
    reconstructed = rk.graph.Entity(entity_id="same", name="Reconstructed")

    assert first == reconstructed
    assert hash(first) == hash(reconstructed)
    assert first.__eq__(object()) is NotImplemented
    assert first != object()


def test_entity_fields_are_validated():
    with pytest.raises(TypeError, match="name"):
        rk.graph.Entity(name=1)
    with pytest.raises(TypeError, match="classification"):
        rk.graph.Entity(classification="building")
    with pytest.raises(TypeError, match="characteristics"):
        rk.graph.Entity(characteristics={})
    with pytest.raises(TypeError, match="provenance"):
        rk.graph.Entity(provenance="source")


def test_entity_characteristics_defaults_and_convenience_properties():
    first = rk.graph.Entity()
    second = rk.graph.Entity()
    office = classification("office")

    first.features["balcony"] = True
    first.occupancy["use"] = (office,)

    assert first.features is first.characteristics.features
    assert first.measures is first.characteristics.measures
    assert first.occupancy is first.characteristics.occupancy
    assert second.features == {}
    assert second.occupancy == {}


def test_entity_preserves_supplied_characteristics_and_provenance():
    characteristics = rk.graph.Characteristics(features={"rating": "A"})
    provenance = rk.graph.Provenance(source="source", identifiers={"id": "1"})

    entity = rk.graph.Entity(
        characteristics=characteristics,
        provenance=provenance,
    )

    assert entity.characteristics is characteristics
    assert entity.provenance is provenance


def test_assembly_is_an_entity_with_the_same_domain_fields():
    characteristics = rk.graph.Characteristics(features={"phase": "existing"})
    provenance = rk.graph.Provenance(source="survey")
    kind = classification("portfolio")

    assembly = rk.graph.Assembly(
        entity_id="assembly",
        name="Portfolio",
        classification=kind,
        characteristics=characteristics,
        provenance=provenance,
    )

    assert isinstance(assembly, rk.graph.Entity)
    assert assembly.classification is kind
    assert assembly.features == {"phase": "existing"}
    assert assembly.provenance is provenance


def test_assembly_copies_inputs_and_exposes_read_only_sets():
    entity = rk.graph.Entity(entity_id="building")
    supplied_entities = [entity]
    assembly = rk.graph.Assembly(entities=supplied_entities)
    supplied_entities.clear()

    assert assembly.entities == frozenset({entity})
    assert assembly.relationships == frozenset()
    with pytest.raises(AttributeError):
        assembly.entities = frozenset()
    with pytest.raises(AttributeError):
        assembly.relationships = frozenset()


def test_assembly_defaults_are_isolated():
    first = rk.graph.Assembly()
    second = rk.graph.Assembly()

    first._replace_contents(entities=(rk.graph.Entity(),), relationships=())

    assert first.entities
    assert second.entities == frozenset()


def test_assembly_rejects_different_entities_sharing_an_id():
    first = rk.graph.Entity(entity_id="same")
    second = rk.graph.Entity(entity_id="same")

    with pytest.raises(ValueError, match="different Entity objects"):
        rk.graph.Assembly(entities=(first, second))


def test_assembly_rejects_different_relationships_sharing_an_id():
    entity = rk.graph.Entity(entity_id="entity")
    kind = relationship_classification()
    first = rk.graph.Relationship("entity", "entity", kind, relationship_id="same")
    second = rk.graph.Relationship("entity", "entity", kind, relationship_id="same")

    with pytest.raises(ValueError, match="different Relationship objects"):
        rk.graph.Assembly(entities=(entity,), relationships=(first, second))


def test_assembly_relationship_endpoints_must_be_directly_contained():
    entity = rk.graph.Entity(entity_id="inside")
    relationship = rk.graph.Relationship(
        "inside", "outside", relationship_classification()
    )

    with pytest.raises(ValueError, match="target endpoint"):
        rk.graph.Assembly(entities=(entity,), relationships=(relationship,))


def test_assembly_itself_may_be_a_relationship_endpoint():
    entity = rk.graph.Entity(entity_id="inside")
    relationship = rk.graph.Relationship(
        "assembly", "inside", relationship_classification()
    )

    assembly = rk.graph.Assembly(
        entity_id="assembly",
        entities=(entity,),
        relationships=(relationship,),
    )

    assert assembly.relationships == frozenset({relationship})


def test_nested_assemblies_are_allowed_but_recursive_containment_is_rejected():
    child = rk.graph.Assembly(entity_id="child")
    parent = rk.graph.Assembly(entity_id="parent", entities=(child,))

    assert parent.entities == frozenset({child})
    with pytest.raises(ValueError, match="cycle"):
        child._replace_contents(entities=(parent,), relationships=())


def test_assembly_cannot_include_itself_by_identity():
    duplicate_identity = rk.graph.Entity(entity_id="assembly")

    with pytest.raises(ValueError, match="cannot contain itself"):
        rk.graph.Assembly(entity_id="assembly", entities=(duplicate_identity,))
