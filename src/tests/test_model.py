import pytest

import rangekeeper as rk


def entity_classification(code="entity.building", name="Building"):
    return rk.graph.Classification(code=code, name=name, scheme="project")


def relationship_classification(code="relationship.contains", name="Contains"):
    return rk.graph.Classification(code=code, name=name, scheme="project")


def test_model_is_public_and_starts_empty():
    model = rk.graph.Model()

    assert rk.graph.model.Model is rk.graph.Model
    assert model.entities() == ()
    assert model.relationships() == ()
    assert model.assemblies() == ()
    assert not hasattr(model, "graph")
    assert model.validate().is_valid


def test_entity_registration_lookup_and_enumeration_are_canonical():
    root = entity_classification("entity", "Entity")
    building_kind = root.define(code="entity.building", name="Building")
    building = rk.graph.Entity(entity_id="building", classification=building_kind)
    model = rk.graph.Model()

    model.add_entity(building)
    model.add_entity(building)

    assert model.entity("building") is building
    assert model.entities() == (building,)
    assert model.classifications() == (root, building_kind)
    assert model.validate().is_valid
    with pytest.raises(rk.graph.MissingEntityError):
        model.entity("missing")


def test_entity_batches_reject_identity_conflicts_atomically():
    existing = rk.graph.Entity(entity_id="existing")
    model = rk.graph.Model()
    model.add_entity(existing)
    added = rk.graph.Entity(entity_id="added")
    conflict = rk.graph.Entity(entity_id="existing")

    with pytest.raises(rk.graph.IdentityConflictError, match="existing"):
        model.add_entities((added, conflict))

    assert model.entities() == (existing,)
    with pytest.raises(rk.graph.MissingEntityError):
        model.entity("added")


def test_classification_key_conflicts_are_rejected_atomically():
    first_kind = entity_classification()
    second_kind = entity_classification(name="A different definition")
    first = rk.graph.Entity(entity_id="first", classification=first_kind)
    second = rk.graph.Entity(entity_id="second", classification=second_kind)
    model = rk.graph.Model()
    model.add_entity(first)

    with pytest.raises(rk.graph.IdentityConflictError, match="classification key"):
        model.add_entity(second)

    assert model.entities() == (first,)


def test_relationship_endpoints_must_be_registered_and_batch_is_atomic():
    source = rk.graph.Entity(entity_id="source")
    target = rk.graph.Entity(entity_id="target")
    kind = relationship_classification()
    valid = rk.graph.Relationship("source", "target", kind, relationship_id="valid")
    dangling = rk.graph.Relationship(
        "source", "missing", kind, relationship_id="dangling"
    )
    model = rk.graph.Model()
    model.add_entities((source, target))

    with pytest.raises(rk.graph.MissingEntityError):
        model.add_relationships((valid, dangling))

    assert model.relationships() == ()
    assert model.validate().is_valid


def test_relationship_identity_conflicts_are_rejected_atomically():
    source = rk.graph.Entity(entity_id="source")
    target = rk.graph.Entity(entity_id="target")
    kind = relationship_classification()
    existing = rk.graph.Relationship("source", "target", kind, relationship_id="same")
    conflict = rk.graph.Relationship("target", "source", kind, relationship_id="same")
    added = rk.graph.Relationship("target", "source", kind, relationship_id="added")
    model = rk.graph.Model()
    model.add_entities((source, target))
    model.add_relationship(existing)

    with pytest.raises(rk.graph.IdentityConflictError, match="same"):
        model.add_relationships((added, conflict))

    assert model.relationships() == (existing,)


def test_relate_accepts_entity_instances_and_ids():
    source = rk.graph.Entity(entity_id="source")
    target = rk.graph.Entity(entity_id="target")
    kind = relationship_classification()
    characteristics = rk.graph.Characteristics(features={"distance": 3})
    provenance = rk.graph.Provenance(source="survey")
    model = rk.graph.Model()
    model.add_entities((source, target))

    relationship = model.relate(
        source,
        "target",
        kind,
        relationship_id="related",
        characteristics=characteristics,
        provenance=provenance,
    )

    assert model.relationship("related") is relationship
    assert relationship.source_id == "source"
    assert relationship.target_id == "target"
    assert relationship.characteristics is characteristics
    assert relationship.provenance is provenance


def test_internal_networkx_representation_uses_canonical_keys_and_objects():
    source = rk.graph.Entity(entity_id="source")
    target = rk.graph.Entity(entity_id="target")
    relationship = rk.graph.Relationship(
        "source",
        "target",
        relationship_classification(),
        relationship_id="relationship",
    )
    model = rk.graph.Model()
    model.add_entities((source, target))
    model.add_relationship(relationship)

    assert model._graph.nodes["source"]["entity"] is source
    assert (
        model._graph["source"]["target"]["relationship"]["relationship"] is relationship
    )


def test_add_assembly_recursively_registers_exact_contents():
    contains = relationship_classification()
    leaf = rk.graph.Entity(entity_id="leaf")
    child_relationship = rk.graph.Relationship(
        "child", "leaf", contains, relationship_id="child-leaf"
    )
    child = rk.graph.Assembly(
        entity_id="child",
        entities=(leaf,),
        relationships=(child_relationship,),
    )
    root_relationship = rk.graph.Relationship(
        "root", "child", contains, relationship_id="root-child"
    )
    root = rk.graph.Assembly(
        entity_id="root",
        entities=(child,),
        relationships=(root_relationship,),
    )
    model = rk.graph.Model()

    model.add_assembly(root)

    assert set(model.entities()) == {root, child, leaf}
    assert set(model.relationships()) == {root_relationship, child_relationship}
    assert model.entity("child") is child
    assert model.relationship("child-leaf") is child_relationship
    assert model.validate().is_valid


def test_add_entity_routes_assemblies_through_recursive_registration():
    child = rk.graph.Entity(entity_id="child")
    assembly = rk.graph.Assembly(entity_id="assembly", entities=(child,))
    model = rk.graph.Model()

    model.add_entity(assembly)

    assert model.entities() == (assembly, child)
    assert model.validate().is_valid


def test_entities_and_relationships_can_belong_to_multiple_assemblies():
    first = rk.graph.Entity(entity_id="first")
    second = rk.graph.Entity(entity_id="second")
    relationship = rk.graph.Relationship(
        "first",
        "second",
        relationship_classification(),
        relationship_id="shared",
    )
    left = rk.graph.Assembly(
        entity_id="left",
        entities=(first, second),
        relationships=(relationship,),
    )
    right = rk.graph.Assembly(
        entity_id="right",
        entities=(first, second),
        relationships=(relationship,),
    )
    model = rk.graph.Model()

    model.add_assembly(left)
    model.add_assembly(right)

    assert model.assemblies_of_entity(first) == (left, right)
    assert model.assemblies_of_relationship(relationship) == (left, right)
    assert model.relationships() == (relationship,)
    assert model.validate().is_valid


def test_assembly_collision_rejects_the_complete_addition_atomically():
    canonical = rk.graph.Entity(entity_id="shared")
    model = rk.graph.Model()
    model.add_entity(canonical)
    conflicting = rk.graph.Entity(entity_id="shared")
    assembly = rk.graph.Assembly(entity_id="assembly", entities=(conflicting,))

    with pytest.raises(rk.graph.IdentityConflictError, match="shared"):
        model.add_assembly(assembly)

    assert model.entities() == (canonical,)


def test_add_to_assembly_registers_new_contents_atomically():
    assembly = rk.graph.Assembly(entity_id="assembly")
    entity = rk.graph.Entity(entity_id="entity")
    relationship = rk.graph.Relationship(
        "assembly",
        "entity",
        relationship_classification(),
        relationship_id="contains",
    )
    model = rk.graph.Model()
    model.add_assembly(assembly)

    model.add_to_assembly("assembly", entities=(entity,), relationships=(relationship,))

    assert model.entity("entity") is entity
    assert model.relationship("contains") is relationship
    assert assembly.entities == frozenset({entity})
    assert assembly.relationships == frozenset({relationship})
    assert model.validate().is_valid


def test_invalid_add_to_assembly_changes_neither_model_nor_assembly():
    assembly = rk.graph.Assembly(entity_id="assembly")
    entity = rk.graph.Entity(entity_id="entity")
    dangling = rk.graph.Relationship(
        "entity",
        "outside",
        relationship_classification(),
        relationship_id="dangling",
    )
    model = rk.graph.Model()
    model.add_assembly(assembly)

    with pytest.raises(rk.graph.InvalidAssemblyError, match="outside"):
        model.add_to_assembly(
            assembly,
            entities=(entity,),
            relationships=(dangling,),
        )

    assert model.entities() == (assembly,)
    assert model.relationships() == ()
    assert assembly.entities == frozenset()


def test_remove_from_assembly_validates_the_complete_proposed_result():
    entity = rk.graph.Entity(entity_id="entity")
    relationship = rk.graph.Relationship(
        "assembly",
        "entity",
        relationship_classification(),
        relationship_id="contains",
    )
    assembly = rk.graph.Assembly(
        entity_id="assembly",
        entities=(entity,),
        relationships=(relationship,),
    )
    model = rk.graph.Model()
    model.add_assembly(assembly)

    with pytest.raises(rk.graph.InvalidAssemblyError, match="target endpoint"):
        model.remove_from_assembly(assembly, entities=(entity,))

    assert assembly.entities == frozenset({entity})
    assert assembly.relationships == frozenset({relationship})

    model.remove_from_assembly(
        assembly,
        entities=("entity",),
        relationships=("contains",),
    )
    assert assembly.entities == frozenset()
    assert assembly.relationships == frozenset()
    assert model.entity("entity") is entity
    assert model.relationship("contains") is relationship


def test_private_recursive_assembly_corruption_is_rejected_on_registration():
    first = rk.graph.Assembly(entity_id="first")
    second = rk.graph.Assembly(entity_id="second")
    first._entities.add(second)
    second._entities.add(first)
    model = rk.graph.Model()

    with pytest.raises(rk.graph.InvalidAssemblyError, match="cycle"):
        model.add_assembly(first)

    assert model.entities() == ()


def test_predecessors_successors_and_classification_filters():
    first = rk.graph.Entity(entity_id="first")
    second = rk.graph.Entity(entity_id="second")
    third = rk.graph.Entity(entity_id="third")
    contains = relationship_classification()
    services = relationship_classification("relationship.services", "Services")
    model = rk.graph.Model()
    model.add_entities((first, second, third))
    model.add_relationships(
        (
            rk.graph.Relationship("first", "second", contains, relationship_id="one"),
            rk.graph.Relationship("first", "second", services, relationship_id="two"),
            rk.graph.Relationship("third", "second", contains, relationship_id="three"),
        )
    )

    assert set(model.predecessors(second)) == {first, third}
    assert model.predecessors("second", services) == (first,)
    assert model.successors(first, "relationship.contains") == (second,)
