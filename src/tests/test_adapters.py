from dataclasses import FrozenInstanceError

import pandas as pd
import pint
import pytest

import rangekeeper as rk


adapter = rk.graph.adapter
table_module = rk.graph.table


def test_supported_adapter_and_table_surfaces_are_explicit():
    assert adapter.__all__ == [
        "AdapterEncodingError",
        "AdapterError",
        "csv",
        "pandas",
        "visualization",
    ]
    assert table_module.__all__ == ["Table", "TableError"]
    for retired in ("json", "speckle", "SpeckleImportError", "SpeckleConflictError"):
        assert not hasattr(adapter, retired)
    assert not hasattr(rk.graph, "materialization")
    for retired in (
        "MaterializationError",
        "Snapshot",
        "SnapshotError",
        "UnsupportedValueError",
    ):
        assert not hasattr(table_module, retired)


def test_table_normalizes_and_freezes_columns_and_rows():
    table = table_module.Table(
        columns=["name", "value"],
        rows=[{"value": 1, "name": "First"}],
    )

    assert table.columns == ("name", "value")
    assert tuple(table.rows[0]) == table.columns
    assert table.column("value") == (1,)
    assert not hasattr(table, "group_by")
    with pytest.raises(TypeError):
        table.rows[0]["value"] = 2
    with pytest.raises(FrozenInstanceError):
        table.columns = ("changed",)


@pytest.mark.parametrize(
    ("columns", "rows", "message"),
    (
        (("",), (), "non-empty strings"),
        (("name", "name"), (), "duplicates"),
        (("name",), ({"name": "First", "extra": 1},), "extra"),
        (("name", "value"), ({"name": "First"},), "missing"),
    ),
)
def test_table_rejects_invalid_columns_and_rows(columns, rows, message):
    with pytest.raises(table_module.TableError, match=message):
        table_module.Table(columns=columns, rows=rows)


def test_table_rejects_string_columns_and_non_mapping_rows():
    with pytest.raises(TypeError, match="iterable of strings"):
        table_module.Table(columns="name", rows=())
    with pytest.raises(TypeError, match="only mappings"):
        table_module.Table(columns=("name",), rows=("First",))


def test_pandas_table_round_trip_preserves_columns_rows_and_runtime_values():
    runtime_value = object()
    table = table_module.Table(
        columns=("entity_id", "value"),
        rows=(
            {"entity_id": "first", "value": runtime_value},
            {"entity_id": "second", "value": None},
        ),
    )

    frame = adapter.pandas.to_dataframe(table)
    restored = adapter.pandas.from_dataframe(frame)

    assert tuple(frame.columns) == table.columns
    assert restored.columns == table.columns
    assert restored.rows[0]["value"] is runtime_value
    assert restored.rows[1]["value"] is None


def test_pandas_adapter_ignores_index_and_preserves_empty_columns():
    frame = pd.DataFrame(columns=("name", "value"), index=pd.Index([], name="index"))

    table = adapter.pandas.from_dataframe(frame)

    assert table.columns == ("name", "value")
    assert table.rows == ()
    assert tuple(adapter.pandas.to_dataframe(table).columns) == table.columns


def test_csv_composes_table_and_dataframe_adapters_with_pandas_inference(tmp_path):
    table = table_module.Table(
        columns=("name", "code", "status", "count", "active", "missing"),
        rows=(
            {
                "name": "Office",
                "code": "001",
                "status": "NA",
                "count": 3,
                "active": True,
                "missing": None,
            },
        ),
    )
    path = tmp_path / "table.csv"

    adapter.csv.write(table, path)
    restored = adapter.csv.read(path)

    assert restored.columns == table.columns
    row = restored.rows[0]
    assert row["name"] == "Office"
    assert row["code"] == 1
    assert pd.isna(row["status"])
    assert row["count"] == 3
    assert row["active"]
    assert pd.isna(row["missing"])


def test_csv_rejects_rich_values_instead_of_stringifying_them(tmp_path):
    table = table_module.Table(
        columns=("labels",),
        rows=({"labels": (("taxonomy", "code"),)},),
    )

    with pytest.raises(adapter.AdapterEncodingError, match="tuple"):
        adapter.csv.write(table, tmp_path / "table.csv")


def test_csv_preserves_empty_tables_and_single_column_none_rows(tmp_path):
    empty = table_module.Table(columns=("name", "value"), rows=())
    empty_path = tmp_path / "empty.csv"
    adapter.csv.write(empty, empty_path)

    missing = table_module.Table(columns=("value",), rows=({"value": None},))
    missing_path = tmp_path / "missing.csv"
    adapter.csv.write(missing, missing_path)

    assert adapter.csv.read(empty_path) == empty
    assert pd.isna(adapter.csv.read(missing_path).column("value")[0])


def test_csv_rejects_non_finite_numbers(tmp_path):
    table = table_module.Table(
        columns=("value",),
        rows=({"value": float("nan")},),
    )

    with pytest.raises(adapter.AdapterEncodingError, match="float"):
        adapter.csv.write(table, tmp_path / "non-finite.csv")


def visualization_fixture():
    entity_root = rk.graph.Classification(code="entity", name="Entity")
    node = rk.graph.Classification(
        code="entity.node",
        name="Node",
        parent=entity_root,
    )
    entity_taxonomy = rk.graph.Taxonomy(
        code="entity",
        name="Entity Types",
        classifications=(entity_root, node),
    )
    relationship_root = rk.graph.Classification(
        code="relationship", name="Relationship"
    )
    contains = rk.graph.Classification(
        code="relationship.contains",
        name="Contains",
        parent=relationship_root,
    )
    taxonomy = rk.graph.Taxonomy(
        code="relationship",
        name="Relationship Types",
        classifications=(relationship_root, contains),
    )
    root = rk.graph.Entity(code="root", name="Root", classification=node)
    child = rk.graph.Entity(code="child", name="Child", classification=node)
    edge = rk.graph.Relationship(
        source_id=root.id,
        target_id=child.id,
        classification=contains,
    )
    graph = rk.graph.Graph(
        definitions=rk.graph.Definitions(taxonomies=(entity_taxonomy, taxonomy)),
        entities=(root, child),
        relationships=(edge,),
    )
    view = rk.graph.View(graph)
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


def test_graph_html_visualization_writes_the_selected_view(tmp_path):
    view, _ = visualization_fixture()

    path = adapter.visualization.graph_html(view, tmp_path / "graph.html")

    contents = path.read_text(encoding="utf-8")
    assert path == tmp_path / "graph.html"
    assert str(view.relationships[0].id) not in contents
    assert "Root" in contents
    assert "Child" in contents
    assert "entity:entity.node" in contents


def test_view_table_includes_taxonomy_code():
    view, _ = visualization_fixture()

    table = table_module.Table.from_view(
        view,
        entity_fields=("entity_id", "taxonomy_code"),
    )

    assert table.column("taxonomy_code") == ("entity", "entity")


def test_view_table_projects_qualified_labels_features_and_missing_values():
    root = rk.graph.Classification(code="entity", name="Entity")
    apartment = rk.graph.Classification(
        code="space.apartment",
        name="Apartment",
        parent=root,
    )
    taxonomy = rk.graph.Taxonomy(
        code="entity",
        name="Entity Types",
        classifications=(root, apartment),
    )
    label = rk.graph.Label(key="use", classifications=(apartment,))
    feature = rk.graph.Feature(name="status", value="active")
    classified = rk.graph.Entity(
        code="classified",
        classification=apartment,
        characteristics=rk.graph.Characteristics(
            labels={"use": label},
            features={"status": feature},
        ),
    )
    missing = rk.graph.Entity(code="missing", classification=root)
    view = rk.graph.Graph(
        definitions=rk.graph.Definitions(taxonomies=(taxonomy,)),
        entities=(classified, missing),
    ).view()

    table = table_module.Table.from_view(
        view,
        entity_fields=("entity_id", "code"),
        labels=("use",),
        features=("status",),
    )

    assert table.rows[0]["label.use"] == (("entity", "space.apartment"),)
    assert table.rows[0]["feature.status"] == "active"
    assert table.rows[1]["label.use"] == ()
    assert table.rows[1]["feature.status"] is None


def test_view_table_converts_measurement_units_and_rejects_incompatible_units():
    measure = rk.graph.Measure(
        code="area.internal",
        name="Internal area",
        units=rk.measure.Index.registry.squaremeter,
    )
    measurement = rk.graph.Measurement(
        measure=measure,
        quantity=1 * rk.measure.Index.registry.squaremeter,
    )
    entity = rk.graph.Entity(
        characteristics=rk.graph.Characteristics(
            measurements={measure.code: measurement}
        )
    )
    view = rk.graph.Graph(
        definitions=rk.graph.Definitions(measures=(measure,)),
        entities=(entity,),
    ).view()

    table = table_module.Table.from_view(
        view,
        measurements={measure: "squarefoot"},
    )

    assert table.rows[0]["measurement.area.internal"] == pytest.approx(10.7639104167)
    with pytest.raises(pint.DimensionalityError):
        table_module.Table.from_view(view, measurements={measure: "second"})


def test_arborescence_table_preserves_relationship_insertion_order():
    relationship = rk.graph.Classification(code="relationship", name="Relationship")
    contains = rk.graph.Classification(
        code="relationship.contains",
        name="Contains",
        parent=relationship,
    )
    taxonomy = rk.graph.Taxonomy(
        code="relationship",
        name="Relationship Types",
        classifications=(relationship, contains),
    )
    root = rk.graph.Entity(code="root")
    first = rk.graph.Entity(code="first")
    second = rk.graph.Entity(code="second")
    to_second = rk.graph.Relationship.between(
        root,
        second,
        classification=contains,
    )
    to_first = rk.graph.Relationship.between(
        root,
        first,
        classification=contains,
    )
    graph = rk.graph.Graph(
        definitions=rk.graph.Definitions(taxonomies=(taxonomy,)),
        entities=(root, first, second),
        relationships=(to_second, to_first),
    )

    table = table_module.Table.from_arborescence(
        graph.view(),
        entity_fields=("code", "entity_id"),
    )

    assert table.columns == ("code", "entity_id", "parent_id")
    assert table.column("entity_id") == (root.id, second.id, first.id)
    assert table.column("parent_id") == (None, root.id, root.id)


def test_arborescence_table_rejects_invalid_views_and_missing_entity_id():
    empty = rk.graph.Graph().view()
    disconnected = rk.graph.Graph(
        entities=(rk.graph.Entity(), rk.graph.Entity()),
    ).view()

    for view in (empty, disconnected):
        with pytest.raises(table_module.TableError, match="arborescence"):
            table_module.Table.from_arborescence(view)
    with pytest.raises(table_module.TableError, match="entity_id"):
        table_module.Table.from_arborescence(
            rk.graph.Graph(entities=(rk.graph.Entity(),)).view(),
            entity_fields=("name",),
        )


def test_arborescence_visualizations_return_plotly_traces():
    _, table = visualization_fixture()

    sunburst = adapter.visualization.sunburst(table, value="total")
    treemap = adapter.visualization.treemap(table, value="total")
    icicle = adapter.visualization.icicle(table, value="total")

    assert tuple(sunburst.ids) == ("root", "child")
    assert tuple(sunburst.parents) == ("", "root")
    assert tuple(sunburst.values) == (2.0, 2.0)
    assert tuple(treemap.labels) == ("Root", "Child")
    assert tuple(icicle.ids) == ("root", "child")
    assert tuple(icicle.parents) == ("", "root")
    assert tuple(icicle.labels) == ("Root", "Child")
    assert tuple(icicle.values) == (2.0, 2.0)


def test_arborescence_visualization_rejects_rich_or_invalid_values():
    _, table = visualization_fixture()
    rich = table_module.Table(
        columns=("entity_id", "parent_id", "name", "total"),
        rows=(
            {
                "entity_id": "root",
                "parent_id": None,
                "name": "Root",
                "total": object(),
            },
        ),
    )

    with pytest.raises(adapter.AdapterEncodingError, match="finite"):
        adapter.visualization.sunburst(rich, value="total")
    with pytest.raises(adapter.AdapterEncodingError, match="missing columns"):
        adapter.visualization.treemap(
            table_module.Table(columns=("entity_id",), rows=()),
        )
