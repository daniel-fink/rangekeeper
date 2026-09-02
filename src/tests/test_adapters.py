import pandas as pd
import pytest

import rangekeeper as rk


adapter = rk.graph.adapter
materialization = rk.graph.materialization


def test_supported_adapter_and_materialization_surfaces_are_explicit():
    assert adapter.__all__ == [
        "AdapterEncodingError",
        "AdapterError",
        "csv",
        "pandas",
        "visualization",
    ]
    assert materialization.__all__ == [
        "MaterializationError",
        "Table",
        "TableError",
    ]
    for retired in ("json", "speckle", "SpeckleImportError", "SpeckleConflictError"):
        assert not hasattr(adapter, retired)
    for retired in ("Snapshot", "SnapshotError", "UnsupportedValueError"):
        assert not hasattr(materialization, retired)


def test_pandas_table_round_trip_preserves_columns_rows_and_runtime_values():
    runtime_value = object()
    table = materialization.Table(
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
    table = materialization.Table(
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
    table = materialization.Table(
        columns=("labels",),
        rows=({"labels": (("taxonomy", "code"),)},),
    )

    with pytest.raises(adapter.AdapterEncodingError, match="tuple"):
        adapter.csv.write(table, tmp_path / "table.csv")


def test_csv_preserves_empty_tables_and_single_column_none_rows(tmp_path):
    empty = materialization.Table(columns=("name", "value"), rows=())
    empty_path = tmp_path / "empty.csv"
    adapter.csv.write(empty, empty_path)

    missing = materialization.Table(columns=("value",), rows=({"value": None},))
    missing_path = tmp_path / "missing.csv"
    adapter.csv.write(missing, missing_path)

    assert adapter.csv.read(empty_path) == empty
    assert pd.isna(adapter.csv.read(missing_path).column("value")[0])


def test_csv_rejects_non_finite_numbers(tmp_path):
    table = materialization.Table(
        columns=("value",),
        rows=({"value": float("nan")},),
    )

    with pytest.raises(adapter.AdapterEncodingError, match="float"):
        adapter.csv.write(table, tmp_path / "non-finite.csv")


def visualization_fixture():
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
    root = rk.graph.Entity(code="root", name="Root")
    child = rk.graph.Entity(code="child", name="Child")
    edge = rk.graph.Relationship(
        source_id=root.id,
        target_id=child.id,
        classification=contains,
    )
    graph = rk.graph.Graph(
        definitions=rk.graph.Definitions(taxonomies=(taxonomy,)),
        entities=(root, child),
        relationships=(edge,),
    )
    view = rk.graph.View(graph)
    table = materialization.Table(
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
    rich = materialization.Table(
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
            materialization.Table(columns=("entity_id",), rows=()),
        )
