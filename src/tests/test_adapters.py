from rangekeeper.visualisation import graph
from dataclasses import FrozenInstanceError
from uuid import uuid4

import numpy as np
import polars as pl
import pint
import pytest

from rangekeeper.shared.errors import EncodingError

import rangekeeper as rk

from rangekeeper.io import polars
from rangekeeper.visualisation import chart
from rangekeeper.shared import table as table_module
from rangekeeper.model import system




def test_table_normalizes_and_freezes_columns_and_rows():
    table = table_module.Table(
        columns=["name", "value"],
        rows=[{"value": 1, "name": "First"}],
    )

    assert table.columns == ("name", "value")
    assert tuple(table.rows[0].values) == table.columns
    assert table.column("value") == (1,)
    assert not hasattr(table, "group_by")
    with pytest.raises(TypeError):
        table.rows[0].values["value"] = 2
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
    with pytest.raises(TypeError, match="must be a mapping"):
        table_module.Table(columns=("name",), rows=("First",))


def test_polars_table_round_trip_preserves_columns_rows_and_runtime_values():
    runtime_value = object()
    table = table_module.Table(
        columns=("entity_id", "value"),
        rows=(
            {"entity_id": "first", "value": runtime_value},
            {"entity_id": "second", "value": None},
        ),
    )

    frame = polars.to_frame(table)
    restored = polars.to_table(frame)

    assert tuple(frame.columns) == table.columns
    assert restored.columns == table.columns
    assert restored.rows[0].values["value"] is runtime_value
    assert restored.rows[1].values["value"] is None


def test_polars_adapter_preserves_empty_columns():
    frame = pl.DataFrame(schema={"name": pl.String, "value": pl.Float64})

    table = polars.to_table(frame)

    assert table.columns == ("name", "value")
    assert table.rows == ()
    assert tuple(polars.to_frame(table).columns) == table.columns














def visualization_fixture():
    from rangekeeper.model import (
        Model,
        Metadata,
        Definitions,
        System,
        Entity,
        Relationship,
        Classification,
        Taxonomy,
    )
    from rangekeeper.model.system import View

    node = Classification(id=uuid4(), code="node", name="Node")
    contains = Classification(
        id=uuid4(), code="contains", name="Contains", parent=node.id
    )
    root = Entity(id=uuid4(), code="root", name="Root", classification=node.id)
    child = Entity(id=uuid4(), code="child", name="Child", classification=node.id)
    edge = Relationship(
        id=uuid4(), source=root.id, target=child.id, classification=contains.id
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        definitions=Definitions(
            taxonomies=(
                Taxonomy(
                    id=uuid4(),
                    code="entity",
                    name="Entity Types",
                    classifications=(node, contains),
                ),
            )
        ),
        system=System(entities=(root, child), relationships=(edge,)),
    )
    view = View(model)
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

    path = graph.graph_html(view, tmp_path / "graph.html")

    contents = path.read_text(encoding="utf-8")
    assert path == tmp_path / "graph.html"
    assert str(view.relationships[0].id) not in contents
    assert "Root" in contents
    assert "Child" in contents
    assert ":node" in contents


@pytest.mark.parametrize("options", ({"physics": float("nan")}, {"x": object()}))
def test_graph_html_wraps_invalid_json_options(tmp_path, options):
    view, _ = visualization_fixture()

    with pytest.raises(EncodingError, match="invalid PyVis options"):
        graph.graph_html(
            view,
            tmp_path / "graph.html",
            options=options,
        )


def test_arborescence_visualizations_return_plotly_traces():
    _, table = visualization_fixture()

    sunburst = chart.sunburst(table, value_column="total")
    treemap = chart.treemap(table, value_column="total")
    icicle = chart.icicle(table, value_column="total")

    assert tuple(sunburst.ids) == ("root", "child")
    assert tuple(sunburst.parents) == ("", "root")
    assert tuple(sunburst.values) == (2.0, 2.0)
    assert tuple(treemap.labels) == ("Root", "Child")
    assert tuple(icicle.ids) == ("root", "child")
    assert tuple(icicle.parents) == ("", "root")
    assert tuple(icicle.labels) == ("Root", "Child")
    assert tuple(icicle.values) == (2.0, 2.0)


def test_arborescence_visualization_rejects_rich_or_invalid_values():
    _, _table = visualization_fixture()
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

    with pytest.raises(EncodingError, match="finite"):
        chart.sunburst(rich, value_column="total")
    with pytest.raises(EncodingError, match="missing columns"):
        chart.treemap(
            table_module.Table(columns=("entity_id",), rows=()),
        )


def test_arborescence_visualization_label_fallback_and_validation():
    table = table_module.Table(
        columns=("entity_id", "parent_id", "name"),
        rows=(
            {"entity_id": "root", "parent_id": None, "name": " "},
            {"entity_id": "child", "parent_id": "root", "name": None},
        ),
    )
    trace = chart.icicle(table)
    assert tuple(trace.labels) == ("root", "child")

    invalid = table_module.Table(
        columns=("entity_id", "parent_id", "name"),
        rows=({"entity_id": "root", "parent_id": None, "name": 42},),
    )
    with pytest.raises(EncodingError, match="strings"):
        chart.icicle(invalid)


@pytest.mark.parametrize(
    ("rows", "message"),
    (
        (
            (
                {"entity_id": "same", "parent_id": None, "name": "Root"},
                {"entity_id": "same", "parent_id": "same", "name": "Child"},
            ),
            "unique",
        ),
        (
            ({"entity_id": "root", "parent_id": "missing", "name": "Root"},),
            "reference a row",
        ),
        (
            (
                {"entity_id": "first", "parent_id": None, "name": "First"},
                {"entity_id": "second", "parent_id": None, "name": "Second"},
            ),
            "one arborescence",
        ),
        (
            (
                {"entity_id": "first", "parent_id": "second", "name": "First"},
                {"entity_id": "second", "parent_id": "first", "name": "Second"},
            ),
            "one arborescence",
        ),
    ),
)
def test_arborescence_visualization_rejects_invalid_topology(rows, message):
    table = table_module.Table(
        columns=("entity_id", "parent_id", "name"),
        rows=rows,
    )
    with pytest.raises(EncodingError, match=message):
        chart.treemap(table)


@pytest.mark.parametrize("value", (True, -1, float("nan"), float("inf")))
def test_arborescence_visualization_rejects_invalid_numeric_values(value):
    table = table_module.Table(
        columns=("entity_id", "parent_id", "name", "total"),
        rows=(
            {
                "entity_id": "root",
                "parent_id": None,
                "name": "Root",
                "total": value,
            },
        ),
    )
    with pytest.raises(EncodingError, match="non-negative"):
        chart.sunburst(table, value_column="total")


def test_arborescence_visualization_rejects_child_totals_above_parent():
    table = table_module.Table(
        columns=("entity_id", "parent_id", "name", "total"),
        rows=(
            {"entity_id": "root", "parent_id": None, "name": "Root", "total": 1},
            {
                "entity_id": "child",
                "parent_id": "root",
                "name": "Child",
                "total": 2,
            },
        ),
    )
    with pytest.raises(EncodingError, match="below child total"):
        chart.icicle(table, value_column="total")






def test_polars_keeps_mixed_and_nested_table_cells():
    table = table_module.Table(
        columns=("mixed", "nested"),
        rows=(
            {"mixed": 1, "nested": ("a", "b")},
            {"mixed": "1", "nested": {"x": 1}},
        ),
    )
    assert polars.to_table(polars.to_frame(table)) == table


def test_table_exports_preserve_large_integers(tmp_path):
    integer = np.int64(2**63 - 1)
    table = table_module.Table(
        columns=("value",), rows=({"value": integer}, {"value": 1.5})
    )
    path = tmp_path / "large.csv"
    polars.text_frame(table).write_csv(path)
    assert path.read_text().splitlines()[1] == str(integer)
    restored = polars.to_table(pl.read_csv(path, schema_overrides={"value": pl.String}))
    assert restored.column("value") == (str(integer), "1.5")
    huge = table_module.Table(columns=("value",), rows=({"value": 10**40},))
    assert polars.to_table(polars.to_frame(huge)) == huge
