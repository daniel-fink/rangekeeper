"""Codes provide scoped names while UUIDs preserve identity."""

from dataclasses import replace

import pytest

from rangekeeper.graph import (
    Assembly,
    Classification,
    Definitions,
    Entity,
    Graph,
    Taxonomy,
    UnknownDefinitionError,
)
from rangekeeper.measure import Index, Measure


def taxonomy(code, class_code="apartment"):
    return Taxonomy(
        code=code,
        name=code,
        classifications=(Classification(code=class_code, name="Apartment"),),
    )


@pytest.mark.parametrize("code", [" A", "A ", "A\n", "\tA", "", " "])
@pytest.mark.parametrize(
    "kind", ["entity", "assembly", "classification", "taxonomy", "measure"]
)
def test_codes_reject_blank_or_surrounding_whitespace(kind, code):
    with pytest.raises(ValueError):
        if kind == "entity":
            Entity(code=code)
        elif kind == "assembly":
            Assembly(code=code)
        elif kind == "classification":
            Classification(code=code, name="Apartment")
        elif kind == "taxonomy":
            taxonomy(code)
        else:
            Measure(code=code, name="Area", units=Index.registry.meter**2)


def test_entity_scope_includes_assemblies_and_allows_missing_codes():
    definitions = Definitions()
    a, lower, unnamed, other = Entity(code="A"), Entity(code="a"), Entity(), Entity()
    graph = Graph(definitions=definitions, entities=(a, lower, unnamed, other))
    assert graph.entity("A") is a
    assert graph.entity("a") is lower
    with pytest.raises(ValueError, match="entity codes must be unique"):
        Graph(definitions=definitions, entities=(a, Assembly(code="A")))
    # Separate graphs may reuse a code for distinct identities.
    another = Entity(code="A")
    assert Graph(definitions=definitions, entities=(another,)).entity("A") is another


def test_uuid_resolution_ignores_duplicate_codes_across_taxonomies():
    first, second = taxonomy("physical"), taxonomy("use")
    a, b = first.classifications["apartment"], second.classifications["apartment"]
    definitions = Definitions(taxonomies=(first, second))
    assert definitions._resolve_classification(a.id) is a
    assert definitions._resolve_classification(b.id) is b
    assert not hasattr(definitions, "classification")


def test_taxonomy_and_classification_codes_allow_literal_dots():
    definition = taxonomy("project.spaces", class_code="space.apartment")
    definitions = Definitions(taxonomies=(definition,))
    item = definition.classifications["space.apartment"]
    assert definitions._resolve_classification(item.id) is item


def test_measure_and_entity_codes_still_allow_literal_dots():
    measure = Measure(
        code="area.net_lettable", name="Area", units=Index.registry.meter**2
    )
    entity = Entity(code="APT.101")
    graph = Graph(definitions=Definitions(measures=(measure,)), entities=(entity,))
    assert graph.entity("APT.101") is entity
    assert graph.definitions.measures["area.net_lettable"] is measure


def test_uuid_shaped_code_does_not_override_identifier_resolution():
    first = taxonomy("physical")
    item = first.classifications["apartment"]
    other = taxonomy("use", class_code=str(item.id))
    definitions = Definitions(taxonomies=(first, other))
    assert definitions._resolve_classification(item.id) is item
    assert other.classifications[str(item.id)].id != item.id


def test_definition_scopes_collisions_and_key_mismatches():
    measure = Measure(code="area", name="Area", units=Index.registry.meter**2)
    first = taxonomy("area")
    # Different catalogues can use the same name.
    definitions = Definitions(taxonomies=(first,), measures=(measure,))
    assert definitions.measures["area"] is measure
    for kwargs in (
        {
            "measures": (
                measure,
                Measure(code="area", name="Other", units=measure.units),
            )
        },
        {"taxonomies": (first, taxonomy("area"))},
        {"measures": {"wrong": measure}},
        {"taxonomies": {"wrong": first}},
    ):
        with pytest.raises(ValueError):
            Definitions(**kwargs)
    with pytest.raises(ValueError, match="codes must be unique"):
        Taxonomy(
            code="duplicate",
            name="Duplicate",
            classifications=(
                Classification(code="a", name="A"),
                Classification(code="a", name="B"),
            ),
        )


def test_code_rename_preserves_uuid_reference_and_changes_only_code_lookup():
    measure = Measure(code="area", name="Area", units=Index.registry.meter**2)
    original = Definitions(measures=(measure,))
    renamed = replace(measure, code="net_area")
    revision = Definitions(measures=(renamed,))
    assert renamed.id == measure.id
    assert revision._resolve_measure(measure.id) is renamed
    assert original.measures["area"] is measure
    assert revision.measures["net_area"] is renamed
    with pytest.raises(UnknownDefinitionError):
        revision.measures["area"]
