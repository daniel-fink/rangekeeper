"""Remaining Graph projection characterizations until external consumer migration."""

import pytest
import pint
import rangekeeper as rk

table_module = rk.legacy.graph.table


def visualization_fixture():
    entity_root = rk.legacy.graph.Classification(code="entity", name="Entity")
    node = rk.legacy.graph.Classification(
        code="node",
        name="Node",
        parent=entity_root,
    )
    entity_taxonomy = rk.legacy.graph.Taxonomy(
        code="entity",
        name="Entity Types",
        classifications=(entity_root, node),
    )
    relationship_root = rk.legacy.graph.Classification(
        code="relationship", name="Relationship"
    )
    contains = rk.legacy.graph.Classification(
        code="contains",
        name="Contains",
        parent=relationship_root,
    )
    taxonomy = rk.legacy.graph.Taxonomy(
        code="relationship",
        name="Relationship Types",
        classifications=(relationship_root, contains),
    )
    root = rk.legacy.graph.Entity(code="root", name="Root", classification=node)
    child = rk.legacy.graph.Entity(code="child", name="Child", classification=node)
    edge = rk.legacy.graph.Relationship(
        source_id=root.id,
        target_id=child.id,
        classification=contains,
    )
    graph = rk.legacy.graph.Graph(
        definitions=rk.legacy.graph.Definitions(taxonomies=(entity_taxonomy, taxonomy)),
        entities=(root, child),
        relationships=(edge,),
    )
    view = rk.legacy.graph.View(graph)
    table = table_module.Table(
        columns=("entity_id", "parent_id", "name", "total"),
        rows=(
            {"entity_id": "root", "parent_id": None, "name": "Root", "total": 2},
            {
                "entity_id": "child",
                "parent_id": "root",
                "name": "Child",
                "total": 2,
            },
        ),
    )
    return view, table


def test_view_table_includes_taxonomy_code():
    view, _ = visualization_fixture()

    table = table_module.Table.from_view(
        view,
        fields=("entity_id", "taxonomy_code"),
    )

    assert table.column("taxonomy_code") == ("entity", "entity")


def test_view_table_default_schema_uses_qualified_domain_fields():
    view, _ = visualization_fixture()

    table = table_module.Table.from_view(view)

    assert table.columns == (
        "entity_id",
        "name",
        "entity_kind",
        "classification_code",
    )
    assert table.column("name") == ("Root", "Child")
    assert table.column("entity_kind") == ("entity", "entity")
    assert table.column("classification_code") == (
        "node",
        "node",
    )


def test_view_table_projects_qualified_labels_features_and_missing_values():
    root = rk.legacy.graph.Classification(code="entity", name="Entity")
    apartment = rk.legacy.graph.Classification(
        code="apartment",
        name="Apartment",
        parent=root,
    )
    taxonomy = rk.legacy.graph.Taxonomy(
        code="entity",
        name="Entity Types",
        classifications=(root, apartment),
    )
    label = rk.legacy.graph.Label(key="use", classifications=(apartment,))
    feature = rk.legacy.graph.Feature(name="status", value="active")
    classified = rk.legacy.graph.Entity(
        code="classified",
        classification=apartment,
        characteristics=rk.legacy.graph.Characteristics(
            labels={"use": label},
            features={"status": feature},
        ),
    )
    missing = rk.legacy.graph.Entity(code="missing", classification=root)
    view = rk.legacy.graph.Graph(
        definitions=rk.legacy.graph.Definitions(taxonomies=(taxonomy,)),
        entities=(classified, missing),
    ).view()

    table = table_module.Table.from_view(
        view,
        fields=("entity_id", "code"),
        labels=("use",),
        features=("status",),
    )

    assert table.rows[0].values["label.use"] == (("entity", "apartment"),)
    assert table.rows[0].values["feature.status"] == "active"
    assert table.rows[1].values["label.use"] == ()
    assert table.rows[1].values["feature.status"] is None


def test_view_table_converts_measure_units_and_rejects_incompatible_units():
    measure = rk.legacy.measure.Measure(
        code="area.internal",
        name="Internal area",
        units=rk.legacy.measure.Index.registry.squaremeter,
    )
    measurement = rk.legacy.graph.Measurement(
        measure=measure,
        quantity=1 * rk.legacy.measure.Index.registry.squaremeter,
    )
    entity = rk.legacy.graph.Entity(
        characteristics=rk.legacy.graph.Characteristics(
            measurements={measure.code: measurement}
        )
    )
    view = rk.legacy.graph.Graph(
        definitions=rk.legacy.graph.Definitions(measures=(measure,)),
        entities=(entity,),
    ).view()

    table = table_module.Table.from_view(
        view,
        measures={measure: "squarefoot"},
    )

    assert table.rows[0].values["measurement.area.internal"] == pytest.approx(
        10.7639104167
    )
    with pytest.raises(pint.DimensionalityError):
        table_module.Table.from_view(view, measures={measure: "second"})


def test_arborescence_table_preserves_relationship_insertion_order():
    relationship = rk.legacy.graph.Classification(code="relationship", name="Relationship")
    contains = rk.legacy.graph.Classification(
        code="contains",
        name="Contains",
        parent=relationship,
    )
    taxonomy = rk.legacy.graph.Taxonomy(
        code="relationship",
        name="Relationship Types",
        classifications=(relationship, contains),
    )
    root = rk.legacy.graph.Entity(code="root")
    first = rk.legacy.graph.Entity(code="first")
    second = rk.legacy.graph.Entity(code="second")
    to_second = rk.legacy.graph.Relationship.between(
        root,
        second,
        classification=contains,
    )
    to_first = rk.legacy.graph.Relationship.between(
        root,
        first,
        classification=contains,
    )
    graph = rk.legacy.graph.Graph(
        definitions=rk.legacy.graph.Definitions(taxonomies=(taxonomy,)),
        entities=(root, first, second),
        relationships=(to_second, to_first),
    )

    table = table_module.Table.from_arborescence(
        graph.view(),
        fields=("code", "entity_id"),
    )

    assert table.columns == ("code", "entity_id", "parent_id")
    assert table.column("entity_id") == (root.id, second.id, first.id)
    assert table.column("parent_id") == (None, root.id, root.id)


def test_arborescence_table_rejects_invalid_views_and_missing_entity_id():
    empty = rk.legacy.graph.Graph().view()
    disconnected = rk.legacy.graph.Graph(
        entities=(rk.legacy.graph.Entity(), rk.legacy.graph.Entity()),
    ).view()

    for view in (empty, disconnected):
        with pytest.raises(table_module.TableError, match="arborescence"):
            table_module.Table.from_arborescence(view)
    with pytest.raises(table_module.TableError, match="entity_id"):
        table_module.Table.from_arborescence(
            rk.legacy.graph.Graph(entities=(rk.legacy.graph.Entity(),)).view(),
            fields=("name",),
        )
