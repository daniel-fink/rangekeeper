from dataclasses import FrozenInstanceError

import networkx as nx
import pytest

import rangekeeper as rk


@pytest.fixture
def graph_fixture():
    taxonomy = rk.graph.Taxonomy(code="project", name="Project")
    root = taxonomy.define(code="project", name="Project")
    building_kind = root.define(code="entity.building", name="Building")
    space_kind = root.define(code="entity.space", name="Space")
    equipment_kind = root.define(code="entity.equipment", name="Equipment")
    contains = root.define(code="relationship.contains", name="Contains")
    services = root.define(code="relationship.services", name="Services")
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
    model.entities.add_all((building, office, retail, plant))
    model.relationships.add_all(relationships)
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

    view = rk.graph.View(model)

    assert rk.graph.view.View is rk.graph.View
    assert view.entities() == model.entities.all()
    assert view.relationships() == model.relationships.all()


def test_entity_classification_and_predicate_filters(graph_fixture):
    model = graph_fixture["model"]

    spaces = rk.graph.View(model, entity_classification="entity.space")
    office = rk.graph.View(model, predicate=lambda entity: entity.name == "Office")

    assert set(spaces.entities()) == {
        graph_fixture["office"],
        graph_fixture["retail"],
    }
    assert spaces.relationships() == ()
    assert office.entities() == (graph_fixture["office"],)


def test_relationship_filter_selects_only_edges_and_their_endpoints(graph_fixture):
    model = graph_fixture["model"]

    contains = rk.graph.View(
        model, relationship_classification=graph_fixture["contains"]
    )
    services = rk.graph.View(
        model, relationship_classification="project:relationship.services"
    )

    assert set(contains.entity_ids) == {"building", "office", "retail"}
    assert set(contains.relationship_ids) == {
        "contains-office",
        "contains-retail",
    }
    assert set(services.entity_ids) == {"plant", "office"}
    assert services.relationship_ids == frozenset({"services-office"})


def test_assembly_view_contains_exact_direct_contents_not_nested_contents():
    contains = rk.graph.Taxonomy(
        code="project.relationship", name="Relationship Types"
    ).define(code="relationship.contains", name="Contains")
    leaf = rk.graph.Entity(entity_id="leaf")
    child = rk.graph.Assembly(entity_id="child", entities=(leaf,))
    root_edge = rk.graph.Relationship(
        "root", "child", contains, relationship_id="root-child"
    )
    root = rk.graph.Assembly(
        entity_id="root", entities=(child,), relationships=(root_edge,)
    )
    model = rk.graph.Model()
    model.assemblies.add(root)

    view = rk.graph.View(model, assembly="root")

    assert view.entity_ids == frozenset({"root", "child"})
    assert view.relationship_ids == frozenset({"root-child"})
    assert "leaf" not in view.entity_ids


def test_view_fields_are_frozen_and_ids_are_frozensets(graph_fixture):
    view = rk.graph.View(graph_fixture["model"])

    assert isinstance(view.entity_ids, frozenset)
    assert isinstance(view.relationship_ids, frozenset)
    with pytest.raises(FrozenInstanceError):
        view.entity_ids = frozenset()


def test_view_filter_is_scoped_to_the_existing_selection(graph_fixture):
    model = graph_fixture["model"]
    contains = rk.graph.View(model, relationship_classification="relationship.contains")

    filtered = contains.filter(predicate=lambda entity: entity.name == "Office")

    assert filtered.entity_ids == frozenset({"office"})
    assert filtered.relationship_ids == frozenset()
    assert "plant" not in filtered.entity_ids


def test_expand_adds_one_hop_with_direction_and_classification(graph_fixture):
    model = graph_fixture["model"]
    office = rk.graph.View(model, predicate=lambda entity: entity.entity_id == "office")

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
    contains = rk.graph.View(model, relationship_classification="relationship.contains")

    assert contains.predecessors("office") == (graph_fixture["building"],)
    assert set(contains.successors("building")) == {
        graph_fixture["office"],
        graph_fixture["retail"],
    }
    with pytest.raises(rk.graph.MissingEntityError):
        contains.predecessors("plant")


def test_roots_leaves_and_arborescence_for_a_tree():
    contains = rk.graph.Taxonomy(
        code="project.relationship", name="Relationship Types"
    ).define(code="contains", name="Contains")
    root = rk.graph.Entity(entity_id="root")
    left = rk.graph.Entity(entity_id="left")
    right = rk.graph.Entity(entity_id="right")
    model = rk.graph.Model()
    model.entities.add_all((root, left, right))
    model.relationships.add_all(
        (
            rk.graph.Relationship(
                "root", "left", contains, relationship_id="left-edge"
            ),
            rk.graph.Relationship(
                "root", "right", contains, relationship_id="right-edge"
            ),
        )
    )
    view = rk.graph.View(model)

    assert view.roots() == (root,)
    assert view.leaves() == (left, right)
    assert view.is_arborescence()


def test_multi_parent_view_is_not_an_arborescence():
    kind = rk.graph.Taxonomy(
        code="project.relationship", name="Relationship Types"
    ).define(code="contains", name="Contains")
    first = rk.graph.Entity(entity_id="first")
    second = rk.graph.Entity(entity_id="second")
    child = rk.graph.Entity(entity_id="child")
    model = rk.graph.Model()
    model.entities.add_all((first, second, child))
    model.relationships.add_all(
        (
            rk.graph.Relationship(
                "first", "child", kind, relationship_id="first-child"
            ),
            rk.graph.Relationship(
                "second", "child", kind, relationship_id="second-child"
            ),
        )
    )

    assert not rk.graph.View(model).is_arborescence()
    assert not rk.graph.View(rk.graph.Model()).is_arborescence()


def test_networkx_export_is_a_frozen_copy(graph_fixture):
    model = graph_fixture["model"]
    view = rk.graph.View(model, relationship_classification="relationship.contains")

    graph = view.to_networkx()

    assert isinstance(graph, nx.MultiDiGraph)
    assert nx.is_frozen(graph)
    assert graph.nodes["building"]["entity"] is graph_fixture["building"]
    with pytest.raises(nx.NetworkXError):
        graph.add_node("other")
    assert "other" not in rk.graph.View(model).entity_ids


def test_direct_view_construction_validates_ids_and_endpoint_closure(graph_fixture):
    model = graph_fixture["model"]

    with pytest.raises(rk.graph.MissingEntityError):
        rk.graph.View(
            model,
            entity_ids=frozenset({"missing"}),
            relationship_ids=frozenset(),
        )
    with pytest.raises(ValueError, match="endpoint outside"):
        rk.graph.View(
            model,
            entity_ids=frozenset({"building"}),
            relationship_ids=frozenset({"contains-office"}),
        )
    with pytest.raises(ValueError, match="supplied together"):
        rk.graph.View(model, entity_ids=frozenset({"building"}))


def test_classification_filters_validate_types_even_for_empty_models():
    model = rk.graph.Model()

    with pytest.raises(TypeError, match="classification filter"):
        rk.graph.View(model, entity_classification=1)
    with pytest.raises(TypeError, match="classification filter"):
        rk.graph.View(model).expand(relationship=1)
