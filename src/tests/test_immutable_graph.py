from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from types import ModuleType
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

import pint
import pandas as pd
import pytest

import rangekeeper as rk
import rangekeeper.graph.aggregation as aggregation_module
import rangekeeper.graph.definitions as definitions_module
from rangekeeper.measure import AggregationRule, Index, Measure, QuantityKind


@pytest.fixture
def model():
    space = rk.graph.Classification(code="space", name="Space")
    apartment = rk.graph.Classification(
        code="space.apartment",
        name="Apartment",
        parent=space,
    )
    parking = rk.graph.Classification(
        code="space.parking",
        name="Parking space",
        parent=space,
    )
    entity_taxonomy = rk.graph.Taxonomy(
        code="entity",
        name="Entity classes",
        classifications=(space, apartment, parking),
    )
    relationship = rk.graph.Classification(code="relationship", name="Relationship")
    contains = rk.graph.Classification(
        code="relationship.contains",
        name="Contains",
        parent=relationship,
    )
    allocated_to = rk.graph.Classification(
        code="relationship.allocated_to",
        name="Allocated to",
        parent=relationship,
    )
    relationship_taxonomy = rk.graph.Taxonomy(
        code="relationship",
        name="Relationship classes",
        classifications=(relationship, contains, allocated_to),
    )
    internal_area = Measure(
        code="area.nsa.internal",
        name="Internal net saleable area",
        units=Index.registry.squaremeter,
        quantity_kind=QuantityKind.AREA,
        aggregation=AggregationRule.SUM,
    )
    definitions = rk.graph.Definitions(
        taxonomies=(entity_taxonomy, relationship_taxonomy),
        measures=(internal_area,),
    )
    return {
        "definitions": definitions,
        "space": space,
        "apartment": apartment,
        "parking": parking,
        "contains": contains,
        "allocated_to": allocated_to,
        "internal_area": internal_area,
    }


def apartment(model, *, code="27.05", feature=None, measurement=None):
    features = {} if feature is None else {feature.name: feature}
    measurements = (
        {} if measurement is None else {measurement.measure.code: measurement}
    )
    return rk.graph.Entity(
        code=code,
        name=f"Apartment {code}",
        classification=model["apartment"],
        characteristics=rk.graph.Characteristics(
            measurements=measurements,
            features=features,
        ),
    )


def asserted(value, *, code="manual.assertion"):
    return rk.graph.Claim(
        value=value,
        kind=rk.graph.ClaimKind.ASSERTED,
        method=rk.graph.Method(code=code),
    )


def test_uuid_defaults_and_deterministic_uuid5(model):
    deterministic = uuid5(NAMESPACE_URL, "mandarin/apartment/27.05")
    entity = rk.graph.Entity(id=deterministic)
    assert isinstance(rk.graph.Entity().id, UUID)
    assert entity.id == deterministic
    with pytest.raises(TypeError, match="UUID"):
        rk.graph.Entity(id="apartment:27.05")


def test_retired_mutable_and_embedded_provenance_apis_are_absent():
    assert not hasattr(rk.graph, "Provenance")
    assert not hasattr(rk.graph, "EntityRegistry")
    assert not hasattr(rk.graph.Classification, "child_of")
    assert not hasattr(rk.graph.Graph(), "connect")
    assert not hasattr(rk.graph.Graph(), "validate")
    assert not hasattr(rk.graph.Characteristics(), "measures")
    assert not hasattr(rk.graph.View, "aggregate_measurement")
    assert not hasattr(rk.graph.View, "aggregate_feature")
    assert not hasattr(rk.graph, "Result")
    assert not hasattr(rk.graph, "FeatureAggregationRule")
    assert hasattr(rk.graph, "Aggregation")
    assert not hasattr(rk.graph, "AggregationResult")
    assert not hasattr(rk.graph, "measurement")
    assert not hasattr(rk.graph, "feature")
    assert not hasattr(rk.graph.Aggregation, "by_measure")
    assert not hasattr(rk.graph.Aggregation, "by_feature")
    assert not hasattr(aggregation_module, "AggregationSpec")
    assert not hasattr(aggregation_module, "_BoundAggregation")
    assert not hasattr(definitions_module, "_DefinitionsIndex")
    assert not hasattr(rk.graph, "Catalog")
    assert isinstance(rk.graph.reduce, ModuleType)


def test_reduction_factories_validate_requests():
    assert isinstance(
        rk.graph.reduce.by_feature("value", reducer=rk.graph.collect),
        rk.graph.reduce.Reduction,
    )
    with pytest.raises(TypeError, match="measure code or Measure"):
        rk.graph.reduce.by_measure(42)
    with pytest.raises(ValueError, match="measure code must not be empty"):
        rk.graph.reduce.by_measure(" ")
    with pytest.raises(TypeError, match="feature name must be a string"):
        rk.graph.reduce.by_feature(42, reducer=any)
    with pytest.raises(ValueError, match="feature name must not be empty"):
        rk.graph.reduce.by_feature(" ", reducer=any)
    with pytest.raises(TypeError, match="feature reducer must be callable"):
        rk.graph.reduce.by_feature("value", reducer=None)
    with pytest.raises(TypeError, match="must be a Reduction"):
        rk.graph.Graph().view().aggregate(object())


def test_taxonomy_is_frozen_single_root_and_acyclic():
    root = rk.graph.Classification(code="root", name="Root")
    child = rk.graph.Classification(code="child", name="Child", parent=root)
    grandchild = rk.graph.Classification(
        code="grandchild",
        name="Grandchild",
        parent=child,
    )
    sibling = rk.graph.Classification(code="sibling", name="Sibling", parent=root)
    taxonomy = rk.graph.Taxonomy(
        code="example",
        name="Example",
        classifications=(root, child, grandchild, sibling),
    )
    assert taxonomy.root is root
    assert taxonomy.is_a(child, root)
    assert taxonomy.is_a(grandchild, root)
    assert not taxonomy.is_a(sibling, child)
    assert taxonomy.children(root) == (child, sibling)
    assert taxonomy.ancestors(grandchild) == (root, child)
    assert taxonomy.descendants(root) == (child, grandchild, sibling)
    assert child.parent is root
    assert not hasattr(taxonomy, "parent")
    assert not hasattr(taxonomy, "_children_index")
    with pytest.raises(TypeError, match="parent must be a Classification"):
        rk.graph.Classification(code="invalid", name="Invalid", parent=root.id)
    with pytest.raises(FrozenInstanceError):
        root.name = "Changed"
    with pytest.raises(ValueError, match="exactly one root"):
        rk.graph.Taxonomy(
            code="bad",
            name="Bad",
            classifications=(root, rk.graph.Classification(code="other", name="Other")),
        )
    equivalent_root = replace(root)
    noncanonical_child = replace(child, parent=equivalent_root)
    with pytest.raises(ValueError, match="registered taxonomy instance"):
        rk.graph.Taxonomy(
            code="noncanonical",
            name="Noncanonical",
            classifications=(root, noncanonical_child),
        )
    first_id, second_id = uuid4(), uuid4()
    with pytest.raises(ValueError, match="acyclic"):
        first = rk.graph.Classification(id=first_id, code="a", name="A")
        second = rk.graph.Classification(
            id=second_id,
            code="b",
            name="B",
            parent=first,
        )
        object.__setattr__(first, "parent", second)
        rk.graph.Taxonomy(
            code="cycle",
            name="Cycle",
            classifications=(
                first,
                second,
                rk.graph.Classification(code="root", name="Root"),
            ),
        )


def test_definitions_and_measure_validation(model):
    measure = model["internal_area"]
    measure.validate_quantity(10 * Index.registry.squaremeter)
    with pytest.raises(pint.DimensionalityError):
        measure.validate_quantity(10 * Index.registry.meter)
    with pytest.raises(ValueError, match="incompatible"):
        Measure(
            code="bad.area",
            name="Bad area",
            units=Index.registry.meter,
            quantity_kind=QuantityKind.AREA,
        )
    duplicate = replace(measure, id=uuid4())
    with pytest.raises(ValueError, match="measure codes"):
        rk.graph.Definitions(measures=(measure, duplicate))
    duplicate_id = replace(measure, id=model["definitions"].taxonomies["entity"].id)
    with pytest.raises(rk.graph.IdentityConflictError, match="definition UUID"):
        rk.graph.Definitions(
            taxonomies=model["definitions"].taxonomies,
            measures=(duplicate_id,),
        )
    with pytest.raises(TypeError, match="Taxonomy objects"):
        rk.graph.Definitions(taxonomies=(measure,))
    with pytest.raises(TypeError, match="Measure objects"):
        rk.graph.Definitions(measures=(model["definitions"].taxonomies["entity"],))
    with pytest.raises(TypeError, match="Classification objects"):
        rk.graph.Taxonomy(
            code="invalid",
            name="Invalid",
            classifications=(measure,),
        )


def test_catalog_inputs_normalize_from_iterables_and_mappings(model):
    definitions = model["definitions"]
    copied = rk.graph.Definitions(
        taxonomies=(item for item in definitions.taxonomies.values()),
        measures=definitions.measures,
    )
    assert copied.taxonomies == definitions.taxonomies
    assert copied.measures == definitions.measures

    original = definitions.taxonomies["entity"]
    copied_taxonomy = rk.graph.Taxonomy(
        id=original.id,
        code=original.code,
        name=original.name,
        definition=original.definition,
        classifications=original.classifications,
    )
    assert copied_taxonomy.classifications == original.classifications

    with pytest.raises(ValueError, match="classification mapping key"):
        rk.graph.Taxonomy(
            code="invalid",
            name="Invalid",
            classifications={"wrong": original.root},
        )
    with pytest.raises(ValueError, match="taxonomy mapping key"):
        rk.graph.Definitions(taxonomies={"wrong": original})
    with pytest.raises(ValueError, match="measure mapping key"):
        rk.graph.Definitions(measures={"wrong": model["internal_area"]})


def test_classification_codes_are_unique_within_a_taxonomy(model):
    root = model["space"]
    duplicate = replace(model["apartment"], id=uuid4())
    with pytest.raises(ValueError, match="classification codes"):
        rk.graph.Taxonomy(
            code="invalid",
            name="Invalid",
            classifications=(root, model["apartment"], duplicate),
        )


def test_identifiable_characteristics_and_keyed_views(model):
    label = rk.graph.Label(key="use", classifications=(model["apartment"],))
    measurement = rk.graph.Measurement(
        measure=model["internal_area"],
        quantity=153 * Index.registry.squaremeter,
    )
    feature = rk.graph.Feature(name="has_study", value=False)
    characteristics = rk.graph.Characteristics(
        labels={"use": label},
        measurements={"area.nsa.internal": measurement},
        features={"has_study": feature},
    )
    entity = apartment(model)
    entity = replace(entity, characteristics=characteristics)
    assert characteristics.label("use") is label
    assert characteristics.measurement(model["internal_area"]) is measurement
    assert characteristics.feature("has_study") is feature
    assert entity.labels["use"] is label
    assert entity.measurements["area.nsa.internal"] is measurement
    assert entity.features["has_study"] is feature
    assert entity.labels is characteristics.labels
    assert entity.measurements is characteristics.measurements
    assert entity.features is characteristics.features
    assert not hasattr(characteristics, "labels_by_key")
    assert not hasattr(characteristics, "measurements_by_measure_id")
    assert not hasattr(characteristics, "features_by_name")
    with pytest.raises(ValueError, match="must match Feature.name"):
        rk.graph.Characteristics(features={"different_name": feature})
    with pytest.raises(TypeError):
        characteristics.features["has_study"] = rk.graph.Feature(
            name="has_study", value=True
        )


def test_feature_values_may_be_arbitrary_and_are_shallowly_immutable():
    values = (
        None,
        "area.nsa.internal",
        True,
        3,
        153.5,
        uuid4(),
        datetime(2026, 8, 28, tzinfo=timezone.utc),
    )
    assert (
        tuple(rk.graph.Feature(name="value", value=value).value for value in values)
        == values
    )

    referenced = ["draft"]
    feature = rk.graph.Feature(name="workflow", value=referenced)
    assert feature.value is referenced
    referenced.append("reviewed")
    assert feature.value == ["draft", "reviewed"]
    with pytest.raises(FrozenInstanceError):
        feature.value = []


def test_characteristic_uuid_uniqueness_is_enforced_by_graph(model):
    first = rk.graph.Feature(name="bedrooms", value=3)
    duplicate = replace(first, name="bathrooms", value=2)
    first_entity = apartment(model, feature=first)
    second_entity = apartment(model, code="27.06", feature=duplicate)

    with pytest.raises(rk.graph.IdentityConflictError, match="graph object"):
        rk.graph.Graph(
            definitions=model["definitions"],
            entities=(first_entity, second_entity),
        )


def test_graph_requires_canonical_definitions(model):
    entity = apartment(model)
    graph = rk.graph.Graph(definitions=model["definitions"], entities=(entity,))
    assert graph.entity(entity.id) is entity
    noncanonical = replace(model["apartment"])
    with pytest.raises(ValueError, match="canonical"):
        rk.graph.Graph(
            definitions=model["definitions"],
            entities=(replace(entity, classification=noncanonical),),
        )


def test_catalog_normalizes_validates_and_preserves_mapping_semantics():
    from rangekeeper.graph._catalog import Catalog

    first = rk.graph.Classification(code="A", name="First")
    second = rk.graph.Classification(code="B", name="Second")
    catalog = Catalog.from_input(
        {"A": first, "B": second},
        item_type=rk.graph.Classification,
        field="classifications",
        kind="classification",
        scope="test catalog",
    )

    assert tuple(catalog) == ("A", "B")
    assert tuple(catalog.values()) == (first, second)
    assert not hasattr(catalog, "_values")
    assert catalog["A"] is first
    assert catalog == {"A": first, "B": second}
    assert {"A": first, "B": second} == catalog

    reordered = Catalog.from_input(
        (second, first),
        item_type=rk.graph.Classification,
        field="classifications",
        kind="classification",
    )
    assert reordered == catalog
    assert hash(reordered) == hash(catalog)

    assert catalog._lookup_id(first.id) is first
    assert catalog._contains_id(first.id)
    assert catalog._require_catalog_instance(first) is first
    with pytest.raises(rk.graph.CatalogInstanceError):
        catalog._require_catalog_instance(replace(first))
    with pytest.raises(rk.graph.UnknownDefinitionError, match="test catalog"):
        catalog._lookup_id(uuid4())
    with pytest.raises(TypeError, match="classification id must be a UUID"):
        catalog._lookup_id("A")
    with pytest.raises(TypeError):
        catalog["A"] = second

    with pytest.raises(
        TypeError,
        match="classifications must contain only Classification objects",
    ):
        Catalog.from_input(
            (first, object()),
            item_type=rk.graph.Classification,
            field="classifications",
            kind="classification",
        )
    with pytest.raises(
        ValueError,
        match="classification mapping key 'wrong' does not match classification code 'A'",
    ):
        Catalog.from_input(
            {"wrong": first},
            item_type=rk.graph.Classification,
            field="classifications",
            kind="classification",
        )


def test_semantic_definition_and_entity_lookup(model):
    definitions = model["definitions"]
    entity_taxonomy = definitions.taxonomies["entity"]
    assert definitions.taxonomies.get("entity") is entity_taxonomy
    assert definitions.taxonomies.get("missing") is None
    assert tuple(definitions.taxonomies) == ("entity", "relationship")
    assert tuple(definitions.taxonomies.values()) == (
        entity_taxonomy,
        definitions.taxonomies["relationship"],
    )
    assert tuple(definitions.taxonomies.items()) == (
        ("entity", entity_taxonomy),
        ("relationship", definitions.taxonomies["relationship"]),
    )
    assert len(definitions.taxonomies) == 2
    assert entity_taxonomy.classifications["space.apartment"] is model["apartment"]
    assert definitions.measures["area.nsa.internal"] is model["internal_area"]
    assert definitions._lookup[entity_taxonomy.id] == (entity_taxonomy, None)
    assert definitions._lookup[model["apartment"].id] == (
        model["apartment"],
        entity_taxonomy,
    )
    assert definitions._lookup[model["internal_area"].id] == (
        model["internal_area"],
        None,
    )
    with pytest.raises(TypeError):
        definitions._lookup[uuid4()] = (entity_taxonomy, None)
    assert not hasattr(definitions, "_definition_by_id")
    assert not hasattr(definitions, "_taxonomy_by_classification_id")
    assert entity_taxonomy.children(model["space"]) == (
        model["apartment"],
        model["parking"],
    )
    with pytest.raises(TypeError):
        definitions.taxonomies["other"] = entity_taxonomy
    assert not hasattr(definitions.taxonomies, "by_id")
    assert not hasattr(definitions.taxonomies, "canonical")

    first = apartment(model, code="27.05")
    repeated = apartment(model, code="27.05")
    named = apartment(model, code="27.06")
    graph = rk.graph.Graph(
        definitions=definitions,
        entities=(first, repeated, named),
    )
    assert graph.find_entities(code="27.05") == (first, repeated)
    assert graph.find_entities(name="Apartment 27.05") == (first, repeated)
    expected_apartments = (
        first,
        repeated,
        named,
    )
    assert graph.find_entities(classification=model["apartment"]) == expected_apartments
    assert (
        graph.find_entities(classification=model["apartment"].id) == expected_apartments
    )
    with pytest.raises(rk.graph.CatalogInstanceError):
        graph.find_entities(classification=replace(model["apartment"]))
    with pytest.raises(TypeError, match="UUID, Classification, or None"):
        graph.find_entities(classification="space.apartment")
    with pytest.raises(rk.graph.AmbiguousLookupError):
        graph.entity("27.05")
    assert graph.entity("27.06") is named


def test_classification_codes_are_scoped_to_taxonomy(model):
    root = rk.graph.Classification(code="other", name="Other")
    duplicate = rk.graph.Classification(
        code="space.apartment",
        name="Duplicate apartment",
        parent=root,
    )
    taxonomy = rk.graph.Taxonomy(
        code="other", name="Other", classifications=(root, duplicate)
    )
    definitions = rk.graph.Definitions(
        taxonomies=(*model["definitions"].taxonomies.values(), taxonomy),
        measures=model["definitions"].measures,
    )
    assert (
        definitions.taxonomies["entity"].classifications["space.apartment"]
        is model["apartment"]
    )
    assert (
        definitions.taxonomies["other"].classifications["space.apartment"] is duplicate
    )


def test_definition_lookup_facades_are_absent(model):
    definitions = model["definitions"]
    for name in (
        "taxonomy",
        "taxonomy_by_id",
        "canonical_taxonomy",
        "find_taxonomy",
        "classification",
        "classification_by_id",
        "canonical_classification",
        "find_classification",
        "measure",
        "measure_by_id",
        "canonical_measure",
        "find_measure",
        "taxonomy_of",
        "taxonomy_for",
        "contains_definition_id",
    ):
        assert not hasattr(definitions, name)
    for name in (
        "classification",
        "classification_by_id",
        "canonical_classification",
        "find",
    ):
        assert not hasattr(definitions.taxonomies["entity"], name)


def test_definition_lookup_errors_include_kind_and_scope(model):
    definitions = model["definitions"]
    with pytest.raises(
        rk.graph.UnknownDefinitionError,
        match="unknown taxonomy 'missing' in Definitions",
    ):
        definitions.taxonomies["missing"]
    with pytest.raises(
        rk.graph.CatalogInstanceError,
        match="classification .* is not the registered instance in taxonomy 'entity'",
    ):
        definitions.taxonomies["entity"].children(replace(model["apartment"]))


def test_taxonomy_hierarchy_requires_canonical_classifications(model):
    taxonomy = model["definitions"].taxonomies["entity"]
    with pytest.raises(TypeError, match="Classification"):
        taxonomy.children("space")
    with pytest.raises(TypeError, match="Classification"):
        taxonomy.children(model["space"].id)


def test_relationship_and_assembly_validation(model):
    unit = apartment(model)
    level = rk.graph.Assembly(
        name="Level 27",
        classification=model["space"],
        entity_ids=frozenset({unit.id}),
    )
    edge = rk.graph.Relationship.between(
        level,
        unit,
        classification=model["contains"],
    )
    level = replace(level, relationship_ids=frozenset({edge.id}))
    graph = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(level, unit),
        relationships=(edge,),
    )
    assert graph.assemblies == (level,)
    assert graph.source_of(edge) is level
    assert graph.target_of(edge) is unit
    assert graph.outgoing(level, classification=model["contains"]) == (edge,)
    assert graph.incoming(unit, classification=model["contains"]) == (edge,)
    assert graph.relationships_between(level, unit) == (edge,)
    assert graph.entities_in(level) == (unit,)
    assert graph.relationships_in(level) == (edge,)
    with pytest.raises(FrozenInstanceError):
        edge.source_id = unit.id
    with pytest.raises(rk.graph.MissingEntityError):
        rk.graph.Graph(
            definitions=model["definitions"],
            entities=(unit,),
            relationships=(edge,),
        )


def test_assembly_factory_retains_uuid_membership(model):
    unit = apartment(model)
    parking = rk.graph.Entity(code="B4-001", classification=model["parking"])
    allocation = rk.graph.Relationship.between(
        parking, unit, classification=model["allocated_to"]
    )
    assembly = rk.graph.Assembly.of(
        entities=(unit, parking),
        relationships=(allocation,),
        code="allocation-1",
        classification=model["space"],
    )
    assert assembly.entity_ids == frozenset({unit.id, parking.id})
    assert assembly.relationship_ids == frozenset({allocation.id})


def test_claim_kind_requirements_and_direct_dependencies():
    edition = rk.graph.SourceEdition(name="JLL pricing", checksum="sha256:abc")
    location = rk.graph.SpreadsheetLocation(
        edition=edition,
        worksheet="Unit Pricing",
        range="F302",
    )
    sourced = rk.graph.Claim(
        value=153,
        kind=rk.graph.ClaimKind.SOURCED,
        sources=(location,),
    )
    derived = rk.graph.Claim(
        value=164,
        kind=rk.graph.ClaimKind.DERIVED,
        sources=(sourced,),
        method=rk.graph.Method(code="sum.nsa.components", version="1"),
    )
    assert derived.sources == (sourced,)
    with pytest.raises(ValueError, match="SpreadsheetLocation"):
        rk.graph.Claim(value=1, kind=rk.graph.ClaimKind.SOURCED)
    with pytest.raises(ValueError, match="method"):
        rk.graph.Claim(
            value=1,
            kind=rk.graph.ClaimKind.DERIVED,
            sources=(sourced,),
        )


def test_claim_and_state_factories(model):
    edition = rk.graph.SourceEdition(name="JLL pricing", checksum="sha256:abc")
    location = rk.graph.SpreadsheetLocation(
        edition=edition, worksheet="Unit Pricing", range="F302"
    )
    method = rk.graph.Method(code="parse.jll", version="1")
    sourced = rk.graph.Claim.sourced(153, at=location, method=method)
    derived = rk.graph.Claim.derived(
        164,
        from_claims=(sourced,),
        method=rk.graph.Method(code="sum.nsa.components"),
    )
    asserted_claim = rk.graph.Claim.asserted(
        164, method=rk.graph.Method(code="review.assertion")
    )
    assert sourced.kind is rk.graph.ClaimKind.SOURCED
    assert derived.sources == (sourced,)
    assert asserted_claim.kind is rk.graph.ClaimKind.ASSERTED

    entity = apartment(model)
    relationship = rk.graph.Relationship.between(
        entity, entity, classification=model["allocated_to"]
    )
    assembly = rk.graph.Assembly.of(
        entities=(entity,), code="assembly", classification=model["space"]
    )
    assert rk.graph.EntityState.from_entity(entity).code == entity.code
    assert (
        rk.graph.RelationshipState.from_relationship(relationship).source_id
        == entity.id
    )
    assert rk.graph.AssemblyState.from_assembly(assembly).entity_ids == frozenset(
        {entity.id}
    )


def test_claim_uuid_uniqueness_is_global_in_graph(model):
    first_feature = rk.graph.Feature(name="bedrooms", value=3)
    second_feature = rk.graph.Feature(name="bathrooms", value=2)
    entity = apartment(model)
    entity = replace(
        entity,
        characteristics=rk.graph.Characteristics(
            features={"bedrooms": first_feature, "bathrooms": second_feature}
        ),
    )
    first_claim = asserted(3)
    duplicate_id = replace(first_claim, value=2)
    with pytest.raises(rk.graph.IdentityConflictError, match="Claims share UUID"):
        rk.graph.Graph(
            definitions=model["definitions"],
            entities=(entity,),
            provenance=(
                rk.graph.Fact(target=first_feature, claims=(first_claim,)),
                rk.graph.Fact(target=second_feature, claims=(duplicate_id,)),
            ),
        )


def test_source_edition_uuid_references_are_canonical(model):
    edition = rk.graph.SourceEdition(name="JLL", checksum="sha256:abc")
    conflicting_edition = replace(edition, name="Different JLL edition")
    first_feature = rk.graph.Feature(name="bedrooms", value=3)
    second_feature = rk.graph.Feature(name="bathrooms", value=2)
    entity = apartment(model)
    entity = replace(
        entity,
        characteristics=rk.graph.Characteristics(
            features={"bedrooms": first_feature, "bathrooms": second_feature}
        ),
    )
    first_claim = rk.graph.Claim.sourced(
        3,
        at=rk.graph.SpreadsheetLocation(edition=edition, worksheet="Units", range="A1"),
    )
    second_claim = rk.graph.Claim.sourced(
        2,
        at=rk.graph.SpreadsheetLocation(
            edition=conflicting_edition, worksheet="Units", range="B1"
        ),
    )
    with pytest.raises(rk.graph.IdentityConflictError, match="SourceEditions"):
        rk.graph.Graph(
            definitions=model["definitions"],
            entities=(entity,),
            provenance=(
                rk.graph.Fact(target=first_feature, claims=(first_claim,)),
                rk.graph.Fact(target=second_feature, claims=(second_claim,)),
            ),
        )


def test_claim_dependency_cycles_are_rejected(model):
    feature = rk.graph.Feature(name="bedrooms", value=3)
    entity = apartment(model, feature=feature)
    first = asserted(3, code="first")
    second = rk.graph.Claim(
        value=3,
        kind=rk.graph.ClaimKind.ASSERTED,
        sources=(first,),
        method=rk.graph.Method(code="second"),
    )
    object.__setattr__(first, "sources", (second,))
    with pytest.raises(ValueError, match="acyclic"):
        rk.graph.Graph(
            definitions=model["definitions"],
            entities=(entity,),
            provenance=(rk.graph.Fact(target=feature, claims=(first,)),),
        )


def test_fact_states_and_reconciliation(model):
    feature = rk.graph.Feature(name="bathrooms", value=2)
    entity = apartment(model, feature=feature)
    first = asserted(2, code="jll")
    second = asserted(2, code="m3")
    matched = rk.graph.Fact(target=feature, claims=(first, second))
    graph = rk.graph.Graph(
        definitions=model["definitions"], entities=(entity,), provenance=(matched,)
    )
    assert graph.fact_for(feature) is matched
    assert matched.status is rk.graph.FactStatus.MATCHED
    conflicting = rk.graph.Fact(target=feature, claims=(first, asserted(3)))
    assert conflicting.status is rk.graph.FactStatus.CONFLICT
    with pytest.raises(ValueError, match="conflicting claims"):
        rk.graph.Graph(
            definitions=model["definitions"],
            entities=(entity,),
            provenance=(conflicting,),
        )
    provisional = replace(
        conflicting,
        reconciliation=rk.graph.Reconciliation(
            selected=first,
            status=rk.graph.ReconciliationStatus.PROVISIONAL,
            method=rk.graph.Method(code="prefer.jll"),
        ),
    )
    graph = replace(graph, provenance=(provisional,))
    assert graph.fact_for(feature).status is rk.graph.FactStatus.PROVISIONAL


def test_measurement_and_entity_state_facts(model):
    measurement = rk.graph.Measurement(
        measure=model["internal_area"],
        quantity=153 * Index.registry.squaremeter,
    )
    entity = apartment(model, measurement=measurement)
    measurement_fact = rk.graph.Fact(
        target=measurement,
        claims=(asserted(153 * Index.registry.squaremeter),),
    )
    state = rk.graph.EntityState(
        code=entity.code,
        name=entity.name,
        classification=entity.classification,
    )
    entity_fact = rk.graph.Fact(target=entity, claims=(asserted(state),))
    graph = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(entity,),
        provenance=(measurement_fact, entity_fact),
    )
    assert (
        graph.fact_for(measurement).current_claim.value.units
        == Index.registry.squaremeter
    )


def test_apply_is_atomic_and_requires_fact_replacement(model):
    feature = rk.graph.Feature(name="bathrooms", value=2)
    entity = apartment(model, feature=feature)
    fact = rk.graph.Fact(target=feature, claims=(asserted(2),))
    graph = rk.graph.Graph(
        definitions=model["definitions"], entities=(entity,), provenance=(fact,)
    )
    changed_feature = replace(feature, value=3)
    changed_entity = replace(
        entity,
        characteristics=rk.graph.Characteristics(
            features={"bathrooms": changed_feature}
        ),
    )
    with pytest.raises(ValueError, match="canonical"):
        graph.apply(rk.graph.GraphChange(replace_entities=(changed_entity,)))
    assert graph.entity(entity.id) is entity
    changed_fact = rk.graph.Fact(target=changed_feature, claims=(asserted(3),))
    updated = graph.apply(
        rk.graph.GraphChange(
            replace_entities=(changed_entity,),
            replace_facts=(changed_fact,),
        )
    )
    assert updated.entity(entity.id) is changed_entity
    assert graph.entity(entity.id) is entity


def test_entity_removal_rejects_dependencies_then_cascades(model):
    unit = apartment(model)
    level = rk.graph.Assembly(
        name="Level 27",
        classification=model["space"],
        entity_ids=frozenset({unit.id}),
    )
    edge = rk.graph.Relationship(
        source_id=level.id,
        target_id=unit.id,
        classification=model["contains"],
    )
    level = replace(level, relationship_ids=frozenset({edge.id}))
    fact = rk.graph.Fact(
        target=unit,
        claims=(
            asserted(
                rk.graph.EntityState(
                    code=unit.code,
                    name=unit.name,
                    classification=unit.classification,
                )
            ),
        ),
    )
    graph = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(level, unit),
        relationships=(edge,),
        provenance=(fact,),
    )
    with pytest.raises(ValueError, match="cascade"):
        graph.without_entities(unit.id)
    child = graph.without_entities(unit.id, cascade=True)
    assert unit not in child.entities
    assert edge not in child.relationships
    assert child.entity(level.id).entity_ids == frozenset()
    assert child.fact_for(unit.id) is None
    assert unit in graph.entities


def test_view_traversal_and_pure_aggregation(model):
    root_feature = rk.graph.Feature(name="requires_review", value=False)
    leaf_feature = rk.graph.Feature(name="requires_review", value=True)
    root = rk.graph.Entity(
        name="Root",
        classification=model["space"],
        characteristics=rk.graph.Characteristics(
            features={"requires_review": root_feature}
        ),
    )
    leaf = apartment(model, feature=leaf_feature)
    unrelated = rk.graph.Entity(code="unrelated", classification=model["parking"])
    edge = rk.graph.Relationship.between(
        root,
        leaf,
        classification=model["contains"],
    )
    graph = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(root, leaf, unrelated),
        relationships=(edge,),
    )
    view = graph.view(relationship_classification=model["contains"])
    assert view.entities == (root, leaf)
    results = view.aggregate(rk.graph.reduce.by_feature("requires_review", reducer=any))
    assert results[root] is True
    assert results[leaf] is True
    assert results[leaf.id] is True
    assert results.root_value is True
    assert results.items() == ((root, True), (leaf, True))
    unanimous = view.aggregate(
        rk.graph.reduce.by_feature("requires_review", reducer=all)
    )
    assert unanimous[root] is False
    assert unanimous[leaf] is True
    assert "subtotal" not in root.features
    assert view.successors(root) == (leaf,)
    assert view.to_networkx().is_directed()


def test_feature_aggregation_collects_raw_subtree_values(model):
    root_feature = rk.graph.Feature(name="planning_zone", value="commercial")
    root = rk.graph.Entity(
        name="Root",
        classification=model["space"],
        characteristics=rk.graph.Characteristics(
            features={"planning_zone": root_feature}
        ),
    )
    first = apartment(
        model,
        code="A",
        feature=rk.graph.Feature(name="planning_zone", value="commercial"),
    )
    second = apartment(
        model,
        code="B",
        feature=rk.graph.Feature(name="planning_zone", value="residential"),
    )
    relationships = (
        rk.graph.Relationship.between(root, first, classification=model["contains"]),
        rk.graph.Relationship.between(root, second, classification=model["contains"]),
    )
    view = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(root, first, second),
        relationships=relationships,
    ).view()

    collected = view.aggregate(
        rk.graph.reduce.by_feature("planning_zone", reducer=rk.graph.collect)
    )
    assert isinstance(collected, rk.graph.Aggregation)
    assert collected.root_value == ("commercial", "commercial", "residential")
    assert collected[first] == ("commercial",)
    assert collected.items() == (
        (root, ("commercial", "commercial", "residential")),
        (first, ("commercial",)),
        (second, ("residential",)),
    )

    unique = view.aggregate(
        rk.graph.reduce.by_feature("planning_zone", reducer=rk.graph.distinct)
    )
    assert unique.root_value == ("commercial", "residential")

    most_common = view.aggregate(
        rk.graph.reduce.by_feature("planning_zone", reducer=rk.graph.mode)
    )
    assert most_common.root_value == "commercial"

    joined = view.aggregate(
        rk.graph.reduce.by_feature(
            "planning_zone",
            reducer=lambda values: " / ".join(values),
        )
    )
    assert joined.root_value == "commercial / commercial / residential"


def test_distinct_uses_normal_python_equality():
    assert rk.graph.distinct(([1], [1], [2])) == ([1], [2])
    with pytest.raises(ValueError, match="truth value of a Series is ambiguous"):
        rk.graph.distinct((pd.Series((1, 2)), pd.Series((1, 2))))


def test_feature_mode_rejects_ties_and_missing_subtrees_are_none(model):
    root = rk.graph.Entity(name="Root", classification=model["space"])
    first = apartment(
        model,
        code="A",
        feature=rk.graph.Feature(name="planning_zone", value="commercial"),
    )
    second = apartment(
        model,
        code="B",
        feature=rk.graph.Feature(name="planning_zone", value="residential"),
    )
    missing = apartment(model, code="C")
    relationships = tuple(
        rk.graph.Relationship.between(root, child, classification=model["contains"])
        for child in (first, second, missing)
    )
    view = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(root, first, second, missing),
        relationships=relationships,
    ).view()

    collected = view.aggregate(
        rk.graph.reduce.by_feature("planning_zone", reducer=rk.graph.collect)
    )
    assert collected[missing] is None
    with pytest.raises(rk.graph.InvalidAggregationError, match="unique mode"):
        view.aggregate(
            rk.graph.reduce.by_feature("planning_zone", reducer=rk.graph.mode)
        )


def test_view_infers_subgraph_and_aggregates_measurements(model):
    measurement = rk.graph.Measurement(
        measure=model["internal_area"],
        quantity=10 * Index.registry.squaremeter,
    )
    root = rk.graph.Entity(code="root", classification=model["space"])
    leaf = apartment(model, code="27.05", measurement=measurement)
    edge = rk.graph.Relationship.between(root, leaf, classification=model["contains"])
    graph = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(root, leaf),
        relationships=(edge,),
    )

    entity_view = graph.view(entities=(root, "27.05"))
    relationship_view = graph.view(relationships=(edge,))
    assert entity_view.entities == (root, leaf)
    assert entity_view.relationships == (edge,)
    assert relationship_view.entities == (root, leaf)
    assert relationship_view.relationships == (edge,)
    assert entity_view.roots == (root,)
    assert entity_view.leaves == (leaf,)
    assert entity_view.is_arborescence
    assert entity_view.successors(root, via=model["contains"]) == (leaf,)
    assert entity_view.predecessors(leaf, via=model["contains"]) == (root,)

    result = entity_view.aggregate(rk.graph.reduce.by_measure("area.nsa.internal"))
    assert result[root] == 10 * Index.registry.squaremeter
    assert result["27.05"] == 10 * Index.registry.squaremeter
    assert result.root_value == 10 * Index.registry.squaremeter


@pytest.mark.parametrize(
    ("rule", "expected"),
    (
        (AggregationRule.SUM, 30),
        (AggregationRule.MEAN, 15),
        (AggregationRule.MEDIAN, 15),
        (AggregationRule.MINIMUM, 10),
        (AggregationRule.MAXIMUM, 20),
    ),
)
def test_measurement_aggregation_rules(model, rule, expected):
    aggregate_area = replace(
        model["internal_area"],
        id=uuid4(),
        code=f"area.{rule.value}",
        aggregation=rule,
    )
    definitions = rk.graph.Definitions(
        taxonomies=model["definitions"].taxonomies,
        measures=(*model["definitions"].measures.values(), aggregate_area),
    )
    root = rk.graph.Entity(name="Root", classification=model["space"])
    first = apartment(
        model,
        code="A",
        measurement=rk.graph.Measurement(
            measure=aggregate_area,
            quantity=10 * Index.registry.squaremeter,
        ),
    )
    second = apartment(
        model,
        code="B",
        measurement=rk.graph.Measurement(
            measure=aggregate_area,
            quantity=20 * Index.registry.squaremeter,
        ),
    )
    relationships = (
        rk.graph.Relationship.between(root, first, classification=model["contains"]),
        rk.graph.Relationship.between(root, second, classification=model["contains"]),
    )
    view = rk.graph.Graph(
        definitions=definitions,
        entities=(root, first, second),
        relationships=relationships,
    ).view()

    result = view.aggregate(rk.graph.reduce.by_measure(aggregate_area))
    assert result.root_value == expected * Index.registry.squaremeter


def test_measurement_aggregation_normalizes_canonical_units(model):
    root = rk.graph.Entity(name="Root", classification=model["space"])
    first = apartment(
        model,
        code="A",
        measurement=rk.graph.Measurement(
            measure=model["internal_area"],
            quantity=1 * Index.registry.squaremeter,
        ),
    )
    second = apartment(
        model,
        code="B",
        measurement=rk.graph.Measurement(
            measure=model["internal_area"],
            quantity=10.763910416709722 * Index.registry.squarefoot,
        ),
    )
    relationships = tuple(
        rk.graph.Relationship.between(root, child, classification=model["contains"])
        for child in (first, second)
    )
    view = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(root, first, second),
        relationships=relationships,
    ).view()

    result = view.aggregate(rk.graph.reduce.by_measure(model["internal_area"]))
    assert result.root_value.units == Index.registry.squaremeter
    assert result.root_value.magnitude == pytest.approx(2)


def test_measurement_without_aggregation_rule_is_rejected(model):
    non_aggregating = Measure(
        code="area.observed",
        name="Observed area",
        units=Index.registry.squaremeter,
        quantity_kind=QuantityKind.AREA,
        aggregation=AggregationRule.NONE,
    )
    definitions = rk.graph.Definitions(
        taxonomies=model["definitions"].taxonomies,
        measures=(*model["definitions"].measures.values(), non_aggregating),
    )
    measurement = rk.graph.Measurement(
        measure=non_aggregating, quantity=10 * Index.registry.squaremeter
    )
    entity = rk.graph.Entity(
        code="single",
        classification=model["apartment"],
        characteristics=rk.graph.Characteristics(
            measurements={"area.observed": measurement}
        ),
    )
    graph = rk.graph.Graph(definitions=definitions, entities=(entity,))
    with pytest.raises(rk.graph.InvalidAggregationError, match="no aggregation rule"):
        graph.view().aggregate(rk.graph.reduce.by_measure(non_aggregating))


def test_feature_aggregation_supports_rich_values_without_mutating_them(model):
    dates = pd.DatetimeIndex(("2025-01-01", "2025-02-01"))
    first_flow = rk.flux.Flow(
        movements=pd.Series((10.0, 20.0), index=dates),
        units=Index.registry.dimensionless,
        name="first",
    )
    second_flow = rk.flux.Flow(
        movements=pd.Series((1.0, 2.0), index=dates),
        units=Index.registry.dimensionless,
        name="second",
    )
    first_snapshot = first_flow.movements.copy(deep=True)
    second_snapshot = second_flow.movements.copy(deep=True)
    root = rk.graph.Entity(name="Root", classification=model["space"])
    first = apartment(
        model,
        code="A",
        feature=rk.graph.Feature(name="cashflow", value=first_flow),
    )
    second = apartment(
        model,
        code="B",
        feature=rk.graph.Feature(name="cashflow", value=second_flow),
    )
    relationships = tuple(
        rk.graph.Relationship.between(root, child, classification=model["contains"])
        for child in (first, second)
    )
    view = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(root, first, second),
        relationships=relationships,
    ).view()

    def combine(values: tuple[rk.flux.Flow, ...]) -> rk.flux.Flow:
        movements = values[0].movements.copy(deep=True)
        for value in values[1:]:
            movements = movements.add(value.movements, fill_value=0)
        return rk.flux.Flow(
            movements=movements,
            units=values[0].units,
            name="aggregate",
        )

    result = view.aggregate(rk.graph.reduce.by_feature("cashflow", reducer=combine))

    pd.testing.assert_series_equal(
        result.root_value.movements,
        pd.Series((11.0, 22.0), index=dates, name="aggregate"),
    )
    pd.testing.assert_series_equal(first_flow.movements, first_snapshot)
    pd.testing.assert_series_equal(second_flow.movements, second_snapshot)


def test_aggregation_rejects_empty_and_non_arborescent_views(model):
    empty = rk.graph.Graph(definitions=model["definitions"]).view()
    with pytest.raises(rk.graph.InvalidAggregationError, match="empty View"):
        empty.aggregate(rk.graph.reduce.by_feature("value", reducer=rk.graph.collect))

    first = apartment(model, code="A")
    second = apartment(model, code="B")
    disconnected = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(first, second),
    ).view()
    with pytest.raises(rk.graph.InvalidAggregationError, match="arborescence"):
        disconnected.aggregate(
            rk.graph.reduce.by_feature("value", reducer=rk.graph.collect)
        )


def test_revision_diff_infers_deletions_and_provenance_changes(model):
    feature = rk.graph.Feature(name="bedrooms", value=3)
    entity = apartment(model, feature=feature)
    fact = rk.graph.Fact(target=feature, claims=(asserted(3),))
    parent_graph = rk.graph.Graph(
        definitions=model["definitions"], entities=(entity,), provenance=(fact,)
    )
    child_graph = parent_graph.without_entities(entity.id, cascade=True)
    parent = rk.graph.GraphRevision(
        graph=parent_graph,
        created_by="importer",
        created_at=datetime.now(timezone.utc),
    )
    child = rk.graph.GraphRevision(
        graph=child_graph,
        parent_ids=(parent.id,),
        created_by="reviewer",
    )
    diff = child.changes_since(parent)
    assert diff.entities.removed == (entity,)
    assert diff.features.removed == (feature,)
    assert diff.facts.removed == (fact,)
    assert fact in parent.graph.provenance


def test_diff_reports_changed_claims_and_reconciliation(model):
    feature = rk.graph.Feature(name="bedrooms", value=3)
    entity = apartment(model, feature=feature)
    selected = asserted(3, code="jll")
    alternative = asserted(4, code="m3")
    provisional = rk.graph.Fact(
        target=feature,
        claims=(selected, alternative),
        reconciliation=rk.graph.Reconciliation(
            selected=selected,
            status=rk.graph.ReconciliationStatus.PROVISIONAL,
        ),
    )
    parent = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(entity,),
        provenance=(provisional,),
    )
    revised_alternative = replace(
        alternative,
        value=3,
        method=rk.graph.Method(code="m3.corrected"),
    )
    resolved = rk.graph.Fact(
        target=feature,
        claims=(selected, revised_alternative),
        reconciliation=rk.graph.Reconciliation(
            selected=selected,
            status=rk.graph.ReconciliationStatus.CONFIRMED,
            method=rk.graph.Method(code="review.confirmed"),
        ),
    )
    child = parent.apply(rk.graph.GraphChange(replace_facts=(resolved,)))
    diff = child.changes_since(parent)
    assert diff.claims.modified == (
        rk.graph.Modification(before=alternative, after=revised_alternative),
    )
    assert diff.facts.modified == (
        rk.graph.Modification(before=provisional, after=resolved),
    )
    assert (
        diff.facts.modified[0].before.reconciliation.status
        is rk.graph.ReconciliationStatus.PROVISIONAL
    )
    assert (
        diff.facts.modified[0].after.reconciliation.status
        is rk.graph.ReconciliationStatus.CONFIRMED
    )


def test_definition_replacement_is_validated_and_diffed(model):
    parent = rk.graph.Graph(definitions=model["definitions"])
    revised_measure = replace(model["internal_area"], name="Internal NSA")
    definitions = rk.graph.Definitions(
        taxonomies=model["definitions"].taxonomies,
        measures=(revised_measure,),
    )
    child = parent.apply(rk.graph.GraphChange(definitions=definitions))
    assert child.definitions.measures[revised_measure.code] is revised_measure
    assert child.changes_since(parent).measures.modified == (
        rk.graph.Modification(before=model["internal_area"], after=revised_measure),
    )


def test_batch_addition_is_one_atomic_change(model):
    entities = tuple(
        rk.graph.Entity(code=str(index), classification=model["apartment"])
        for index in range(1_000)
    )
    empty = rk.graph.Graph(definitions=model["definitions"])
    graph = empty.apply(rk.graph.GraphChange(add_entities=entities))
    assert len(graph.entities) == 1_000
    assert empty.entities == ()


def test_tabular_and_icicle_projection_use_uuid_graph(model):
    area = rk.graph.Measurement(
        measure=model["internal_area"],
        quantity=10 * Index.registry.squaremeter,
    )
    root = rk.graph.Entity(name="Root", classification=model["space"])
    leaf = apartment(model, measurement=area)
    edge = rk.graph.Relationship.between(
        root,
        leaf,
        classification=model["contains"],
    )
    graph = rk.graph.Graph(
        definitions=model["definitions"],
        entities=(root, leaf),
        relationships=(edge,),
    )
    from rangekeeper.graph.materialization import Table

    table = Table.from_arborescence(
        graph.view(),
        fields=("entity_id", "code", "name"),
        measurements={"area.nsa.internal": None},
    )
    assert "measurement.area.nsa.internal" in table.columns
    assert table.rows[0]["entity_id"] == root.id
    assert table.rows[1]["parent_id"] == root.id
    trace = rk.graph.visualization.icicle(table, label="name")
    assert tuple(trace.ids) == (str(root.id), str(leaf.id))
