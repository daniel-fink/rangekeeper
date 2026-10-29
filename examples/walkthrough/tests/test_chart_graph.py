"""Graph display and hierarchy charts from Rangekeeper tables and Views."""

from uuid import uuid4

import pytest
from helpers import chart, graph

from rangekeeper.shared import table as table_module
from rangekeeper.shared.errors import EncodingError


def visualization_fixture():
    from rangekeeper.model import (
        Classification,
        Definitions,
        Entity,
        Metadata,
        Model,
        Relationship,
        System,
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
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
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
    view = View(model=model)
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
