from dataclasses import FrozenInstanceError

import pint
import pytest

import rangekeeper as rk


materialization = rk.graph.materialization
units = rk.measure.Index.registry


def table_graph():
    entity_types = rk.graph.Taxonomy(code="project.entity", name="Entity Types").define(
        code="entity", name="Entity"
    )
    building_kind = entity_types.define(code="building", name="Building")
    space_kind = entity_types.define(code="space", name="Space")
    uses = rk.graph.Taxonomy(code="ABS FCB", name="Building Uses").define(
        code="use", name="Use"
    )
    office_use = uses.define(code="231", name="Offices")
    retail_use = uses.define(code="233", name="Shops")
    contains = rk.graph.Taxonomy(
        code="project.relationship", name="Relationship Types"
    ).define(code="contains", name="Contains")
    area = rk.measure.Measure(
        code="project.area",
        name="Area",
        units=units.sqm,
        definition="Floor area",
    )
    building = rk.graph.Assembly(
        entity_id="building",
        name="Building",
        classification=building_kind,
        characteristics=rk.graph.Characteristics(
            measures={area: 100 * units.sqm},
            features={"rating": "A"},
        ),
    )
    office = rk.graph.Entity(
        entity_id="office",
        name="Office",
        classification=space_kind,
        characteristics=rk.graph.Characteristics(
            labels={"use": (office_use,)},
            measures={area: 10_000 * units.sqft},
            features={"rating": "B"},
        ),
    )
    mixed = rk.graph.Entity(
        entity_id="mixed",
        name="Mixed Use",
        classification=space_kind,
        characteristics=rk.graph.Characteristics(
            labels={"use": (office_use, retail_use)},
            features={"rating": "C"},
        ),
    )
    relationships = (
        rk.graph.Relationship(
            "building", "office", contains, relationship_id="building-office"
        ),
        rk.graph.Relationship(
            "building", "mixed", contains, relationship_id="building-mixed"
        ),
    )
    building._replace_contents(entities=(office, mixed), relationships=relationships)
    graph = rk.graph.Graph()
    graph.assemblies.add(building)
    return graph, building, office, mixed, contains, area


def test_table_is_rectangular_read_only_and_column_addressable():
    table = materialization.Table(
        columns=("name", "value"),
        rows=({"name": "A", "value": 1}, {"name": "B", "value": 2}),
    )

    assert table.column("value") == (1, 2)
    with pytest.raises(TypeError):
        table.rows[0]["value"] = 3
    with pytest.raises(FrozenInstanceError):
        table.columns = ()
    with pytest.raises(ValueError, match="do not match"):
        materialization.Table(columns=("name",), rows=({"other": "A"},))


def test_table_from_view_owns_column_order_and_selected_fields():
    graph, *_ = table_graph()

    table = materialization.Table.from_view(
        rk.graph.View(graph),
        fields=(
            "entity_id",
            "name",
            "entity_type",
            "classification_code",
            "classification_taxonomy",
        ),
        features=("rating",),
    )

    assert table.columns == (
        "entity_id",
        "name",
        "entity_type",
        "classification_code",
        "classification_taxonomy",
        "feature.rating",
    )
    assert table.column("entity_id") == ("building", "mixed", "office")
    assert table.rows[0]["entity_type"] == "assembly"
    assert table.rows[0]["classification_code"] == "building"
    assert table.rows[0]["classification_taxonomy"] == "project.entity"
    assert table.column("feature.rating") == ("A", "C", "B")


def test_label_projection_is_scheme_aware_and_preserves_all_values():
    graph, _, office, mixed, *_ = table_graph()

    table = materialization.Table.from_view(rk.graph.View(graph), labels=("use",))
    rows = {row["entity_id"]: row for row in table.rows}

    assert rows[office.entity_id]["labels.use"] == (("ABS FCB", "231"),)
    assert rows[mixed.entity_id]["labels.use"] == (
        ("ABS FCB", "231"),
        ("ABS FCB", "233"),
    )


def test_measure_projection_converts_to_target_units_and_uses_numeric_cells():
    graph, building, office, _, _, area = table_graph()

    table = materialization.Table.from_view(
        rk.graph.View(graph), measures={area: units.sqft}
    )
    column = "measure.project.area [squarefoot]"
    rows = {row["entity_id"]: row for row in table.rows}

    assert table.columns[-1] == column
    assert rows[office.entity_id][column] == pytest.approx(10_000)
    assert rows[building.entity_id][column] == pytest.approx(1_076.391)
    assert rows["mixed"][column] is None
    assert not isinstance(rows[office.entity_id][column], pint.Quantity)


def test_default_measure_target_uses_the_measure_definition_units():
    graph, _, office, _, _, area = table_graph()

    table = materialization.Table.from_view(rk.graph.View(graph), measures={area: None})
    column = "measure.project.area [squaremeter]"
    rows = {row["entity_id"]: row for row in table.rows}

    assert rows[office.entity_id][column] == pytest.approx(929.0304)


def test_view_projection_remains_scoped_to_the_view():
    graph, building, office, *_ = table_graph()
    view = rk.graph.View(
        graph, predicate=lambda entity: entity.entity_id in {"building", "office"}
    )

    table = materialization.Table.from_view(view, features=("rating",))

    assert table.column("entity_id") == (building.entity_id, office.entity_id)
    assert table.column("feature.rating") == ("A", "B")


def test_feature_projection_preserves_rich_runtime_values():
    graph, _, office, *_ = table_graph()
    runtime_value = object()
    office.features["runtime"] = runtime_value

    table = materialization.Table.from_view(rk.graph.View(graph), features=("runtime",))
    rows = {row["entity_id"]: row for row in table.rows}

    assert rows[office.entity_id]["feature.runtime"] is runtime_value


def test_arborescence_projection_adds_parent_ids_and_uses_stable_preorder():
    entity_kind = rk.graph.Taxonomy(code="project.entity", name="Entity Types").define(
        code="entity", name="Entity"
    )
    contains = rk.graph.Taxonomy(
        code="project.relationship", name="Relationship Types"
    ).define(code="contains", name="Contains")
    entities = tuple(
        rk.graph.Entity(
            entity_id=entity_id,
            name=entity_id.title(),
            classification=entity_kind,
        )
        for entity_id in ("root", "zulu", "alpha", "alpha-child")
    )
    graph = rk.graph.Graph()
    graph.entities.add_all(entities)
    graph.relationships.add_all(
        (
            rk.graph.Relationship(
                "root", "zulu", contains, relationship_id="root-zulu"
            ),
            rk.graph.Relationship(
                "root", "alpha", contains, relationship_id="root-alpha"
            ),
            rk.graph.Relationship(
                "alpha",
                "alpha-child",
                contains,
                relationship_id="alpha-child",
            ),
        )
    )

    table = materialization.Table.from_arborescence(
        rk.graph.View(graph), fields=("name", "entity_id")
    )

    assert table.columns == ("name", "entity_id", "parent_id")
    assert table.column("entity_id") == (
        "root",
        "alpha",
        "alpha-child",
        "zulu",
    )
    assert table.column("parent_id") == (None, "root", "alpha", "root")


def test_arborescence_projection_preserves_values_including_aggregates():
    graph, building, office, mixed, _, area = table_graph()
    office.features["area"] = 10
    mixed.features["area"] = 20
    view = rk.graph.View(graph)
    view.aggregate(feature="area", into="total_area")

    table = materialization.Table.from_arborescence(
        view,
        fields=("entity_id", "name"),
        labels=("use",),
        measures={area: units.sqm},
        features=("area", "total_area"),
    )
    rows = {row["entity_id"]: row for row in table.rows}

    assert rows[building.entity_id]["parent_id"] is None
    assert rows[office.entity_id]["parent_id"] == building.entity_id
    assert rows[mixed.entity_id]["parent_id"] == building.entity_id
    assert rows[building.entity_id]["feature.total_area"] == 30
    assert rows[office.entity_id]["labels.use"] == (("ABS FCB", "231"),)
    assert rows[building.entity_id]["measure.project.area [squaremeter]"] == 100


def test_single_entity_is_an_arborescence_table():
    graph = rk.graph.Graph()
    graph.entities.add(rk.graph.Entity(entity_id="only"))

    table = materialization.Table.from_arborescence(rk.graph.View(graph))

    assert table.column("entity_id") == ("only",)
    assert table.column("parent_id") == (None,)


def test_arborescence_projection_rejects_invalid_views_and_missing_entity_id():
    graph, *_ = table_graph()
    view = rk.graph.View(graph)

    with pytest.raises(TypeError, match="view must be a View"):
        materialization.Table.from_arborescence(graph)
    with pytest.raises(materialization.TableError, match="require.*entity_id"):
        materialization.Table.from_arborescence(view, fields=("name",))

    empty_view = rk.graph.View(rk.graph.Graph())
    with pytest.raises(materialization.TableError, match="non-empty"):
        materialization.Table.from_arborescence(empty_view)

    disconnected_graph = rk.graph.Graph()
    disconnected_graph.entities.add_all(
        (
            rk.graph.Entity(entity_id="first"),
            rk.graph.Entity(entity_id="second"),
        )
    )
    with pytest.raises(materialization.TableError, match="arborescence"):
        materialization.Table.from_arborescence(rk.graph.View(disconnected_graph))


@pytest.mark.parametrize(
    "edges",
    (
        (("first", "second"), ("second", "first")),
        (("first", "child"), ("second", "child")),
    ),
)
def test_arborescence_projection_rejects_cycles_and_multiple_parents(edges):
    contains = rk.graph.Taxonomy(
        code="project.relationship", name="Relationship Types"
    ).define(code="contains", name="Contains")
    entity_ids = {entity_id for edge in edges for entity_id in edge}
    graph = rk.graph.Graph()
    graph.entities.add_all(
        rk.graph.Entity(entity_id=entity_id) for entity_id in entity_ids
    )
    graph.relationships.add_all(
        rk.graph.Relationship(
            source_id,
            target_id,
            contains,
            relationship_id=f"{source_id}-{target_id}",
        )
        for source_id, target_id in edges
    )

    with pytest.raises(materialization.TableError, match="arborescence"):
        materialization.Table.from_arborescence(rk.graph.View(graph))


def test_arborescence_projection_uses_only_relationships_selected_by_the_view():
    relationship_types = rk.graph.Taxonomy(
        code="project.relationship", name="Relationship Types"
    )
    relationship = relationship_types.define(code="relationship", name="Relationship")
    contains = relationship.define(code="contains", name="Contains")
    services = relationship.define(code="services", name="Services")
    graph = rk.graph.Graph()
    graph.entities.add_all(
        rk.graph.Entity(entity_id=entity_id)
        for entity_id in ("root", "child", "external")
    )
    graph.relationships.add_all(
        (
            rk.graph.Relationship(
                "root", "child", contains, relationship_id="root-child"
            ),
            rk.graph.Relationship(
                "external", "child", services, relationship_id="external-child"
            ),
        )
    )
    view = rk.graph.View(graph, relationship_classification=contains)

    table = materialization.Table.from_arborescence(view)

    assert table.column("entity_id") == ("root", "child")
    assert table.column("parent_id") == (None, "root")


def test_group_by_uses_explicit_functions_and_preserves_first_seen_order():
    table = materialization.Table(
        columns=("use", "area", "count"),
        rows=(
            {"use": "office", "area": 10, "count": 1},
            {"use": "retail", "area": 5, "count": 1},
            {"use": "office", "area": None, "count": 1},
            {"use": "office", "area": 20, "count": 1},
        ),
    )

    grouped = table.group_by(
        by=("use",),
        aggregations={
            "area": lambda values: sum(value for value in values if value is not None),
            "count": sum,
        },
    )

    assert grouped.columns == ("use", "area", "count")
    assert tuple(dict(row) for row in grouped.rows) == (
        {"use": "office", "area": 30, "count": 3},
        {"use": "retail", "area": 5, "count": 1},
    )


def test_table_selection_validation_is_precise():
    graph, *_, area = table_graph()
    view = rk.graph.View(graph)

    with pytest.raises(TypeError, match="view must be a View"):
        materialization.Table.from_view(graph)
    with pytest.raises(materialization.TableError, match="unknown entity fields"):
        materialization.Table.from_view(view, fields=("unknown",))
    with pytest.raises(TypeError, match="not a string"):
        materialization.Table.from_view(view, features="rating")
    with pytest.raises(TypeError, match="Measure keys"):
        materialization.Table.from_view(view, measures={"project.area": None})
    with pytest.raises(pint.DimensionalityError):
        materialization.Table.from_view(view, measures={area: units.meter})
