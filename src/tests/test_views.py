from dataclasses import FrozenInstanceError

import networkx as nx
import pytest

import rangekeeper as rk


@pytest.fixture
def graph_fixture():
    building_kind = rk.graph.Classification(
        code="entity.building", name="Building", scheme="project"
    )
    space_kind = rk.graph.Classification(
        code="entity.space", name="Space", scheme="project"
    )
    equipment_kind = rk.graph.Classification(
        code="entity.equipment", name="Equipment", scheme="project"
    )
    contains = rk.graph.Classification(
        code="relationship.contains", name="Contains", scheme="project"
    )
    services = rk.graph.Classification(
        code="relationship.services", name="Services", scheme="project"
    )
    building = rk.graph.Entity(
        entity_id="building", name="Building", classification=building_kind
    )
    office = rk.graph.Entity(
        entity_id="office", name="Office", classification=space_kind
    )
    retail = rk.graph.Entity(
        entity_id="retail", name="Retail", classification=space_kind
    )
    plant = rk.graph.Entity(
        entity_id="plant", name="Plant", classification=equipment_kind
    )
    relationships = (
        rk.graph.Relationship(
            "building", "office", contains, relationship_id="contains-office"
        ),
        rk.graph.Relationship(
            "building", "retail", contains, relationship_id="contains-retail"
        ),
        rk.graph.Relationship(
            "plant", "office", services, relationship_id="services-office"
        ),
    )
    model = rk.graph.Model()
    model.add_entities((building, office, retail, plant))
    model.add_relationships(relationships)
    return {
        "model": model,
        "building": building,
        "office": office,
        "retail": retail,
        "plant": plant,
        "contains": contains,
        "services": services,
        "relationships": relationships,
    }


def test_full_view_contains_the_complete_model(graph_fixture):
    model = graph_fixture["model"]

    view = model.view()

    assert rk.graph.view.View is rk.graph.View
    assert view.entities() == model.entities()
    assert view.relationships() == model.relationships()


def test_entity_classification_and_predicate_filters(graph_fixture):
    model = graph_fixture["model"]

    spaces = model.view(entity_classification="entity.space")
    office = model.view(predicate=lambda entity: entity.name == "Office")

    assert set(spaces.entities()) == {
        graph_fixture["office"],
        graph_fixture["retail"],
    }
    assert spaces.relationships() == ()
    assert office.entities() == (graph_fixture["office"],)


def test_relationship_filter_selects_only_edges_and_their_endpoints(graph_fixture):
    model = graph_fixture["model"]

    contains = model.view(relationship_classification=graph_fixture["contains"])
    services = model.view(relationship_classification="project:relationship.services")

    assert set(contains.entity_ids) == {"building", "office", "retail"}
    assert set(contains.relationship_ids) == {
        "contains-office",
        "contains-retail",
    }
    assert set(services.entity_ids) == {"plant", "office"}
    assert services.relationship_ids == frozenset({"services-office"})


def test_assembly_view_contains_exact_direct_contents_not_nested_contents():
    contains = rk.graph.Classification(code="relationship.contains", name="Contains")
    leaf = rk.graph.Entity(entity_id="leaf")
    child = rk.graph.Assembly(entity_id="child", entities=(leaf,))
    root_edge = rk.graph.Relationship(
        "root", "child", contains, relationship_id="root-child"
    )
    root = rk.graph.Assembly(
        entity_id="root", entities=(child,), relationships=(root_edge,)
    )
    model = rk.graph.Model()
    model.add_assembly(root)

    view = model.view(assembly="root")

    assert view.entity_ids == frozenset({"root", "child"})
    assert view.relationship_ids == frozenset({"root-child"})
    assert "leaf" not in view.entity_ids


def test_view_fields_are_frozen_and_ids_are_frozensets(graph_fixture):
    view = graph_fixture["model"].view()

    assert isinstance(view.entity_ids, frozenset)
    assert isinstance(view.relationship_ids, frozenset)
    with pytest.raises(FrozenInstanceError):
        view.entity_ids = frozenset()


def test_view_filter_is_scoped_to_the_existing_selection(graph_fixture):
    model = graph_fixture["model"]
    contains = model.view(relationship_classification="relationship.contains")

    filtered = contains.filter(predicate=lambda entity: entity.name == "Office")

    assert filtered.entity_ids == frozenset({"office"})
    assert filtered.relationship_ids == frozenset()
    assert "plant" not in filtered.entity_ids


def test_expand_adds_one_hop_with_direction_and_classification(graph_fixture):
    model = graph_fixture["model"]
    office = model.view(predicate=lambda entity: entity.entity_id == "office")

    incoming_contains = office.expand(
        graph_fixture["contains"], outgoing=False, incoming=True
    )
    outgoing_only = office.expand(outgoing=True, incoming=False)

    assert incoming_contains.entity_ids == frozenset({"office", "building"})
    assert incoming_contains.relationship_ids == frozenset({"contains-office"})
    assert outgoing_only.entity_ids == frozenset({"office"})
    assert outgoing_only.relationship_ids == frozenset()
    with pytest.raises(ValueError, match="outgoing or incoming"):
        office.expand(outgoing=False, incoming=False)


def test_view_predecessors_and_successors_respect_selected_edges(graph_fixture):
    model = graph_fixture["model"]
    contains = model.view(relationship_classification="relationship.contains")

    assert contains.predecessors("office") == (graph_fixture["building"],)
    assert set(contains.successors("building")) == {
        graph_fixture["office"],
        graph_fixture["retail"],
    }
    with pytest.raises(rk.graph.MissingEntityError):
        contains.predecessors("plant")


def test_roots_leaves_and_arborescence_for_a_tree():
    contains = rk.graph.Classification(code="contains", name="Contains")
    root = rk.graph.Entity(entity_id="root")
    left = rk.graph.Entity(entity_id="left")
    right = rk.graph.Entity(entity_id="right")
    model = rk.graph.Model()
    model.add_entities((root, left, right))
    model.add_relationships(
        (
            rk.graph.Relationship(
                "root", "left", contains, relationship_id="left-edge"
            ),
            rk.graph.Relationship(
                "root", "right", contains, relationship_id="right-edge"
            ),
        )
    )
    view = model.view()

    assert view.roots() == (root,)
    assert view.leaves() == (left, right)
    assert view.is_arborescence()


def test_multi_parent_view_is_not_an_arborescence():
    kind = rk.graph.Classification(code="contains", name="Contains")
    first = rk.graph.Entity(entity_id="first")
    second = rk.graph.Entity(entity_id="second")
    child = rk.graph.Entity(entity_id="child")
    model = rk.graph.Model()
    model.add_entities((first, second, child))
    model.add_relationships(
        (
            rk.graph.Relationship(
                "first", "child", kind, relationship_id="first-child"
            ),
            rk.graph.Relationship(
                "second", "child", kind, relationship_id="second-child"
            ),
        )
    )

    assert not model.view().is_arborescence()
    assert not rk.graph.Model().view().is_arborescence()


def test_networkx_export_is_a_frozen_copy(graph_fixture):
    model = graph_fixture["model"]
    view = model.view(relationship_classification="relationship.contains")

    graph = view.to_networkx()

    assert isinstance(graph, nx.MultiDiGraph)
    assert nx.is_frozen(graph)
    assert graph.nodes["building"]["entity"] is graph_fixture["building"]
    with pytest.raises(nx.NetworkXError):
        graph.add_node("other")
    assert "other" not in model.view().entity_ids


def test_direct_view_construction_validates_ids_and_endpoint_closure(graph_fixture):
    model = graph_fixture["model"]

    with pytest.raises(rk.graph.MissingEntityError):
        rk.graph.View(model, frozenset({"missing"}), frozenset())
    with pytest.raises(ValueError, match="endpoint outside"):
        rk.graph.View(
            model,
            frozenset({"building"}),
            frozenset({"contains-office"}),
        )


def test_classification_filters_validate_types_even_for_empty_models():
    model = rk.graph.Model()

    with pytest.raises(TypeError, match="classification filter"):
        model.view(entity_classification=1)
    with pytest.raises(TypeError, match="classification filter"):
        model.view().expand(relationship=1)
