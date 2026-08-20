import pytest

import rangekeeper as rk


def entity_classification(code="entity.building", name="Building"):
    return rk.graph.Taxonomy(code="project", name="Project").define(
        code=code, name=name
    )


def relationship_classification(code="relationship.contains", name="Contains"):
    return rk.graph.Taxonomy(code="project", name="Project").define(
        code=code, name=name
    )


def test_model_is_public_and_starts_empty():
    model = rk.graph.Model()

    assert rk.graph.model.Model is rk.graph.Model
    assert model.entities.all() == ()
    assert model.relationships.all() == ()
    assert model.assemblies.all() == ()
    assert model.taxonomies.all() == ()
    assert not hasattr(model, "add_entity")
    assert not hasattr(model, "views")
    assert not callable(model.entities)
    assert not hasattr(model, "graph")
    assert model.validate().is_valid


def test_entity_registration_lookup_and_enumeration_are_canonical():
    root = entity_classification("entity", "Entity")
    building_kind = root.define(code="entity.building", name="Building")
    building = rk.graph.Entity(entity_id="building", classification=building_kind)
    model = rk.graph.Model()

    assert model.entities.add(building) is building
    assert model.entities.add(building) is building

    assert model.entities["building"] is building
    assert model.entities.get("building") is building
    assert model.entities.get("missing") is None
    assert model.entities.all() == (building,)
    assert model.taxonomies.all() == (root.taxonomy,)
    assert root.taxonomy.classifications() == (root, building_kind)
    assert root.taxonomy.is_frozen
    assert model.validate().is_valid
    with pytest.raises(ValueError, match="frozen"):
        root.define(code="entity.space", name="Space")
    with pytest.raises(rk.graph.MissingEntityError):
        model.entities["missing"]


def test_entity_batches_reject_identity_conflicts_atomically():
    existing = rk.graph.Entity(entity_id="existing")
    model = rk.graph.Model()
    model.entities.add(existing)
    added = rk.graph.Entity(entity_id="added")
    conflict = rk.graph.Entity(entity_id="existing")

    with pytest.raises(rk.graph.IdentityConflictError, match="existing"):
        model.entities.add_all((added, conflict))

    assert model.entities.all() == (existing,)
    with pytest.raises(rk.graph.MissingEntityError):
        model.entities["added"]


def test_taxonomy_code_conflicts_are_rejected_atomically():
    first_kind = entity_classification()
    second_kind = entity_classification(name="A different definition")
    first = rk.graph.Entity(entity_id="first", classification=first_kind)
    second = rk.graph.Entity(entity_id="second", classification=second_kind)
    model = rk.graph.Model()
    model.entities.add(first)

    with pytest.raises(rk.graph.IdentityConflictError, match="taxonomy code"):
        model.entities.add(second)

    assert model.entities.all() == (first,)


def test_taxonomies_can_be_registered_explicitly_as_complete_aggregates():
    taxonomy = rk.graph.Taxonomy(code="uses", name="Uses")
    root = taxonomy.define(code="use", name="Use")
    office = root.define(code="office", name="Office")
    model = rk.graph.Model()

    assert model.taxonomies.add(taxonomy) is taxonomy
    assert model.taxonomies.add(taxonomy) is taxonomy

    assert model.taxonomies["uses"] is taxonomy
    assert model.taxonomies.get("uses") is taxonomy
    assert model.taxonomies.get("missing") is None
    assert model.taxonomies.all() == (taxonomy,)
    assert taxonomy.classifications() == (root, office)
    assert taxonomy.is_frozen


def test_empty_taxonomies_cannot_be_registered():
    model = rk.graph.Model()

    with pytest.raises(ValueError, match="define a root"):
        model.taxonomies.add(rk.graph.Taxonomy(code="empty", name="Empty"))

    assert model.taxonomies.all() == ()


def test_relationship_endpoints_must_be_registered_and_batch_is_atomic():
    source = rk.graph.Entity(entity_id="source")
    target = rk.graph.Entity(entity_id="target")
    kind = relationship_classification()
    valid = rk.graph.Relationship("source", "target", kind, relationship_id="valid")
    dangling = rk.graph.Relationship(
        "source", "missing", kind, relationship_id="dangling"
    )
    model = rk.graph.Model()
    model.entities.add_all((source, target))

    with pytest.raises(rk.graph.MissingEntityError):
        model.relationships.add_all((valid, dangling))

    assert model.relationships.all() == ()
    assert model.validate().is_valid


def test_relationship_identity_conflicts_are_rejected_atomically():
    source = rk.graph.Entity(entity_id="source")
    target = rk.graph.Entity(entity_id="target")
    kind = relationship_classification()
    existing = rk.graph.Relationship("source", "target", kind, relationship_id="same")
    conflict = rk.graph.Relationship("target", "source", kind, relationship_id="same")
    added = rk.graph.Relationship("target", "source", kind, relationship_id="added")
    model = rk.graph.Model()
    model.entities.add_all((source, target))
    model.relationships.add(existing)

    with pytest.raises(rk.graph.IdentityConflictError, match="same"):
        model.relationships.add_all((added, conflict))

    assert model.relationships.all() == (existing,)


def test_relationship_connect_accepts_entity_instances_and_ids():
    source = rk.graph.Entity(entity_id="source")
    target = rk.graph.Entity(entity_id="target")
    kind = relationship_classification()
    characteristics = rk.graph.Characteristics(features={"distance": 3})
    provenance = rk.graph.Provenance(source="survey")
    model = rk.graph.Model()
    model.entities.add_all((source, target))

    relationship = model.relationships.connect(
        source,
        "target",
        kind,
        relationship_id="related",
        characteristics=characteristics,
        provenance=provenance,
    )

    assert model.relationships["related"] is relationship
    assert model.relationships.get("related") is relationship
    assert model.relationships.get("missing") is None
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
    model.entities.add_all((source, target))
    model.relationships.add(relationship)

    assert model._graph.nodes["source"]["entity"] is source
    assert (
        model._graph["source"]["target"]["relationship"]["relationship"] is relationship
    )


def test_assembly_add_recursively_registers_exact_contents():
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

    assert model.assemblies.add(root) is root

    assert model.assemblies["root"] is root
    assert model.assemblies.get("root") is root
    assert model.assemblies.get("missing") is None
    assert set(model.entities.all()) == {root, child, leaf}
    assert set(model.relationships.all()) == {root_relationship, child_relationship}
    assert model.entities["child"] is child
    assert model.relationships["child-leaf"] is child_relationship
    assert model.validate().is_valid


def test_entity_add_routes_assemblies_through_recursive_registration():
    child = rk.graph.Entity(entity_id="child")
    assembly = rk.graph.Assembly(entity_id="assembly", entities=(child,))
    model = rk.graph.Model()

    model.entities.add(assembly)

    assert model.entities.all() == (assembly, child)
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

    model.assemblies.add(left)
    model.assemblies.add(right)

    assert model.assemblies.containing(first) == (left, right)
    assert model.assemblies.containing(relationship) == (left, right)
    assert model.relationships.all() == (relationship,)
    assert model.validate().is_valid


def test_assembly_collision_rejects_the_complete_addition_atomically():
    canonical = rk.graph.Entity(entity_id="shared")
    model = rk.graph.Model()
    model.entities.add(canonical)
    conflicting = rk.graph.Entity(entity_id="shared")
    assembly = rk.graph.Assembly(entity_id="assembly", entities=(conflicting,))

    with pytest.raises(rk.graph.IdentityConflictError, match="shared"):
        model.assemblies.add(assembly)

    assert model.entities.all() == (canonical,)


def test_assembly_include_registers_new_contents_atomically():
    assembly = rk.graph.Assembly(entity_id="assembly")
    entity = rk.graph.Entity(entity_id="entity")
    relationship = rk.graph.Relationship(
        "assembly",
        "entity",
        relationship_classification(),
        relationship_id="contains",
    )
    model = rk.graph.Model()
    model.assemblies.add(assembly)

    assert model.assemblies.include("assembly", entity, relationship) is assembly

    assert model.entities["entity"] is entity
    assert model.relationships["contains"] is relationship
    assert assembly.entities == frozenset({entity})
    assert assembly.relationships == frozenset({relationship})
    assert model.validate().is_valid


def test_invalid_assembly_include_changes_neither_model_nor_assembly():
    assembly = rk.graph.Assembly(entity_id="assembly")
    entity = rk.graph.Entity(entity_id="entity")
    dangling = rk.graph.Relationship(
        "entity",
        "outside",
        relationship_classification(),
        relationship_id="dangling",
    )
    model = rk.graph.Model()
    model.assemblies.add(assembly)

    with pytest.raises(rk.graph.InvalidAssemblyError, match="outside"):
        model.assemblies.include(assembly, entity, dangling)

    assert model.entities.all() == (assembly,)
    assert model.relationships.all() == ()
    assert assembly.entities == frozenset()


def test_assembly_members_must_be_domain_objects():
    assembly = rk.graph.Assembly(entity_id="assembly")
    model = rk.graph.Model()
    model.assemblies.add(assembly)

    with pytest.raises(TypeError, match="Entity or Relationship"):
        model.assemblies.include(assembly, "entity")


def test_assembly_exclude_validates_the_complete_proposed_result():
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
    model.assemblies.add(assembly)

    with pytest.raises(rk.graph.InvalidAssemblyError, match="target endpoint"):
        model.assemblies.exclude(assembly, entity)

    assert assembly.entities == frozenset({entity})
    assert assembly.relationships == frozenset({relationship})

    assert model.assemblies.exclude(assembly, entity, relationship) is assembly
    assert assembly.entities == frozenset()
    assert assembly.relationships == frozenset()
    assert model.entities["entity"] is entity
    assert model.relationships["contains"] is relationship


def test_private_recursive_assembly_corruption_is_rejected_on_registration():
    first = rk.graph.Assembly(entity_id="first")
    second = rk.graph.Assembly(entity_id="second")
    first._entities.add(second)
    second._entities.add(first)
    model = rk.graph.Model()

    with pytest.raises(rk.graph.InvalidAssemblyError, match="cycle"):
        model.assemblies.add(first)

    assert model.entities.all() == ()


def test_predecessors_successors_and_classification_filters():
    first = rk.graph.Entity(entity_id="first")
    second = rk.graph.Entity(entity_id="second")
    third = rk.graph.Entity(entity_id="third")
    taxonomy = rk.graph.Taxonomy(code="project", name="Project")
    root = taxonomy.define(code="relationship", name="Relationship")
    contains = root.define(code="relationship.contains", name="Contains")
    services = root.define(code="relationship.services", name="Services")
    model = rk.graph.Model()
    model.entities.add_all((first, second, third))
    model.relationships.add_all(
        (
            rk.graph.Relationship("first", "second", contains, relationship_id="one"),
            rk.graph.Relationship("first", "second", services, relationship_id="two"),
            rk.graph.Relationship("third", "second", contains, relationship_id="three"),
        )
    )

    assert set(model.entities.predecessors(second)) == {first, third}
    assert model.entities.predecessors("second", services) == (first,)
    assert model.entities.successors(first, "relationship.contains") == (second,)
