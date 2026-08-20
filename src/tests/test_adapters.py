import json as json_library

import pandas as pd
import pytest
from specklepy.api import operations
from specklepy.objects import Base
from specklepy.transports.memory import MemoryTransport

import rangekeeper as rk


adapter = rk.graph.adapter
materialization = rk.graph.materialization


def adapter_model():
    kinds = rk.graph.Taxonomy(code="entity", name="Entity Types")
    kind = kinds.define(code="entity", name="Entity")
    entity = rk.graph.Entity(
        entity_id="entity-1",
        name="Entity One",
        classification=kind,
        characteristics=rk.graph.Characteristics(features={"values": (1, "two", None)}),
    )
    model = rk.graph.Model()
    model.entities.add(entity)
    return model


def test_json_snapshot_text_round_trip_is_deterministic():
    snapshot = materialization.to_snapshot(adapter_model())

    encoded = adapter.json.dumps(snapshot)
    restored = adapter.json.loads(encoded)

    assert restored == snapshot
    assert adapter.json.dumps(restored) == encoded
    assert json_library.loads(encoded)["schema_version"] == 2


def test_json_snapshot_file_round_trip(tmp_path):
    snapshot = materialization.to_snapshot(adapter_model())
    path = tmp_path / "model.json"

    adapter.json.dump(snapshot, path)

    assert adapter.json.load(path) == snapshot


def test_json_adapter_rejects_invalid_boundary_values():
    with pytest.raises(TypeError, match="Snapshot"):
        adapter.json.dumps(adapter_model())
    with pytest.raises(adapter.AdapterEncodingError, match="root"):
        adapter.json.loads("[]")
    with pytest.raises(adapter.AdapterEncodingError, match="invalid Snapshot JSON"):
        adapter.json.loads("{")


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


class LegacyEntity(Base):
    pass


class LegacyAssembly(LegacyEntity):
    pass


class LegacyRelationship(Base):
    pass


def legacy_design():
    office_plain = LegacyEntity(id="office-object", applicationId="office-app")
    office_plain["entityId"] = "office"
    office_plain["name"] = "Office"
    office_plain["type"] = "space"
    office_plain["gfa"] = 100
    office_plain["use"] = "office"

    office_assembly = LegacyAssembly(applicationId="office-assembly-app")
    office_assembly["entityId"] = "office"
    office_assembly["name"] = "Office"
    office_assembly["type"] = "space"
    office_assembly["gfa"] = 100
    office_assembly["use"] = "office"
    office_assembly["relationships"] = []

    building = LegacyAssembly(applicationId="building-app")
    building["entityId"] = "building"
    building["name"] = "Building"
    building["type"] = "building"
    relationship = LegacyRelationship(applicationId="contains-office")
    relationship["source"] = None
    relationship["target"] = office_assembly
    relationship["type"] = "spatiallyContains"
    building["relationships"] = [relationship]

    root = Base()
    root["entities"] = [building, office_plain]
    return root


def test_speckle_legacy_import_reconciles_entities_and_builds_domain_graph(capsys):
    model = adapter.speckle.load(
        legacy_design(),
        context={"project_id": "project", "version_id": "version"},
    )

    office = model.entities["office"]
    building = model.entities["building"]
    relationship = model.relationships["contains-office"]

    assert isinstance(office, rk.graph.Assembly)
    assert isinstance(building, rk.graph.Assembly)
    assert office.features["gfa"] == 100
    assert office.classification.key == ("legacy.entity_type", "space")
    assert office.labels["use"][0].key == ("legacy.labels.use", "office")
    assert relationship.classification.key == (
        "legacy.relationship_type",
        "spatiallyContains",
    )
    assert relationship.source_id == "building"
    assert relationship.target_id == "office"
    assert office in building.entities
    assert relationship in building.relationships
    assert office.provenance.identifiers["project_id"] == "project"
    assert capsys.readouterr().out == ""


def test_speckle_legacy_import_rejects_conflicting_duplicate_features():
    root = legacy_design()
    duplicate = LegacyEntity()
    duplicate["entityId"] = "office"
    duplicate["name"] = "Office"
    duplicate["type"] = "space"
    duplicate["gfa"] = 200
    root["entities"].append(duplicate)

    with pytest.raises(adapter.SpeckleConflictError, match="feature 'gfa'"):
        adapter.speckle.load(root)


def test_speckle_legacy_import_rejects_unsupported_features_without_stringifying():
    root = legacy_design()
    root["entities"][0]["unsupported"] = object()

    with pytest.raises(
        adapter.SpeckleImportError, match="unsupported value type object"
    ):
        adapter.speckle.load(root)


def test_speckle_snapshot_package_round_trip_is_lossless():
    model = adapter_model()

    package = adapter.speckle.dump(model)
    transport = MemoryTransport()
    transported = operations.deserialize(
        operations.serialize(package, write_transports=[transport]),
        read_transport=transport,
    )
    restored = adapter.speckle.load(transported)

    assert package.packageKind == "rangekeeper.snapshot"
    assert not hasattr(package, "graph")
    assert materialization.to_snapshot(restored) == materialization.to_snapshot(model)


def visualization_fixture():
    relationships = rk.graph.Taxonomy(
        code="relationship", name="Relationship Types"
    ).define(code="contains", name="Contains")
    model = rk.graph.Model()
    model.entities.add_all(
        (
            rk.graph.Entity(entity_id="root", name="Root"),
            rk.graph.Entity(entity_id="child", name="Child"),
        )
    )
    model.relationships.connect(
        "root",
        "child",
        relationships,
        relationship_id="root-child",
    )
    view = rk.graph.View(model)
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
    assert "root-child" not in contents
    assert "root" in contents
    assert "child" in contents


def test_arborescence_visualizations_return_plotly_traces():
    _, table = visualization_fixture()

    sunburst = adapter.visualization.sunburst(table, value="total")
    treemap = adapter.visualization.treemap(table, value="total")

    assert tuple(sunburst.ids) == ("root", "child")
    assert tuple(sunburst.parents) == ("", "root")
    assert tuple(sunburst.values) == (2.0, 2.0)
    assert tuple(treemap.labels) == ("Root", "Child")


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
