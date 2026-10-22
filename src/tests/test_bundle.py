"""Standalone schema/Parquet conformance without a source service."""

from copy import deepcopy
from pathlib import Path
from uuid import UUID
import pytest
import yaml

pytest.importorskip("pyarrow")
from rangekeeper import Model
from rangekeeper.io.bundle import Reader, write, identity, model_digest
from rangekeeper.io.migration import model_07_to_08
from rangekeeper.schema.runtime import exact_equal

ROOT = Path(__file__).parents[2]


def test_record_query_filters_in_parquet_without_arrow_materialization(
    tmp_path, monkeypatch
):
    import pyarrow.parquet as pq

    model = Model.from_data(
        dict(
            metadata=dict(id=str(UUID(int=1)), schema_version="0.8.0"),
            system=dict(
                entities=[
                    dict(id=str(UUID(int=i)), name=f"Entity {i}")
                    for i in range(2, 1002)
                ]
            ),
        )
    )
    write(tmp_path / "bundle", model, row_group_size=64)
    reader = Reader(tmp_path / "bundle")

    def forbidden(*args, **kwargs):
        raise AssertionError("Record queries must not materialize an Arrow table")

    monkeypatch.setattr(pq, "read_table", forbidden)
    first = reader.records(kind="Entity", limit=3)
    second = reader.records(kind="Entity", offset=first["next_offset"], limit=3)
    assert len(first["items"]) == len(second["items"]) == 3
    assert not {r["path"] for r in first["items"]} & {
        r["path"] for r in second["items"]
    }
    exact = reader.records(canonical_id=str(UUID(int=555)), limit=1)
    assert len(exact["items"]) == 1 and exact["next_offset"] is None
    assert reader.records(path=exact["items"][0]["path"]) == exact
    assert reader.records(path="' OR 1=1 --")["items"] == []
    with pytest.raises(ValueError):
        reader.records(path=[])


def test_records_page_in_numeric_path_order(tmp_path):
    model = Model.from_data(
        dict(
            metadata=dict(id=str(UUID(int=1)), schema_version="0.8.0"),
            system=dict(
                entities=[
                    dict(id=str(UUID(int=i)), name=f"Entity {i}") for i in range(2, 14)
                ]
            ),
        )
    )
    write(tmp_path / "bundle", model)
    reader = Reader(tmp_path / "bundle")

    paths, offset = [], 0
    while offset is not None:
        page = reader.records(kind="Entity", offset=offset, limit=5)
        paths += [r["path"] for r in page["items"]]
        offset = page["next_offset"]
    assert paths == [f"/system/entities/{i}" for i in range(12)]

    listed = [r["path"] for r in reader.records(limit=1000)["items"]]
    assert listed[0] == ""
    assert listed.index("/system/entities/2") < listed.index("/system/entities/10")


def test_opening_validates_each_retained_document_once(tmp_path, monkeypatch):
    model = Model.from_data(
        yaml.safe_load((ROOT / "examples/schema/model.yaml").read_text())
    )
    write(tmp_path / "bundle", model)
    original = Model.from_data.__func__
    calls = []

    def counted(cls, data, **kwargs):
        calls.append(data["metadata"]["id"])
        return original(cls, data, **kwargs)

    monkeypatch.setattr(Model, "from_data", classmethod(counted))
    reader = Reader(tmp_path / "bundle")
    assert calls == [str(model.id)]
    assert exact_equal(reader.model().to_data(), model.to_data())


def test_index_check_rejects_a_rehashed_index_unless_it_is_skipped(tmp_path):
    import json
    import pyarrow.parquet as pq
    from rangekeeper.io.bundle import inventory

    model = Model.from_data(
        yaml.safe_load((ROOT / "examples/schema/model.yaml").read_text())
    )
    root = tmp_path / "bundle"
    write(root, model)
    index = root / "model/records.parquet"
    table = pq.read_table(index)
    pq.write_table(table.slice(1), index)
    marker = root / "manifest.json"
    manifest = json.loads(marker.read_text())
    manifest["files"] = [
        inventory(root, [e["path"]])[0] if e["path"] == "model/records.parquet" else e
        for e in manifest["files"]
    ]
    marker.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Derived reference index"):
        Reader(root)
    # Skipping trusts an index verified earlier; the files still match their hashes.
    reader = Reader(root, check_index=False)
    assert exact_equal(reader.model().to_data(), model.to_data())
    damaged = index.read_bytes()
    index.write_bytes(damaged[:-1] + bytes([damaged[-1] ^ 1]))
    with pytest.raises(ValueError):
        Reader(root, check_index=False)


@pytest.mark.parametrize(
    "filename", ["model.yaml", "model-forward-output.yaml", "model-inverse-output.yaml"]
)
def test_complete_model_reconstruction_from_schema_tables(tmp_path, filename):
    model = Model.from_data(
        yaml.safe_load((ROOT / "examples/schema" / filename).read_text())
    )
    write(tmp_path / "bundle", model)
    reconstructed = Reader(tmp_path / "bundle").model()
    assert exact_equal(reconstructed.to_data(), model.to_data())
    assert not list((tmp_path / "bundle").rglob("model.json"))


def test_presence_scalar_types_and_collection_order(tmp_path):
    data = yaml.safe_load((ROOT / "examples/schema/model.yaml").read_text())
    model = Model.from_data(data)
    before = model.to_data()
    write(tmp_path / "bundle", model, row_group_size=1)
    assert exact_equal(Reader(tmp_path / "bundle").model().to_data(), before)
    reordered = deepcopy(before)
    for name in ("entities", "relationships", "assemblies"):
        if name in reordered.get("system", {}):
            reordered["system"][name].reverse()
    assert model_digest(Model.from_data(reordered)) == model_digest(model)


def test_unknown_format_unsafe_inventory_and_limits(tmp_path):
    import json

    model = Model.from_data(
        dict(metadata=dict(id=str(UUID(int=1)), schema_version="0.8.0"))
    )
    write(tmp_path / "bundle", model)
    path = tmp_path / "bundle/manifest.json"
    original = json.loads(path.read_text())
    for mutate in (
        lambda m: m.update(format="unknown"),
        lambda m: m["files"][0].update(path="../escape"),
    ):
        changed = deepcopy(original)
        mutate(changed)
        path.write_text(json.dumps(changed))
        with pytest.raises(ValueError):
            Reader(tmp_path / "bundle")
    path.write_text(json.dumps(original))
    with pytest.raises(ValueError):
        Reader(tmp_path / "bundle", max_rows=1)


def test_old_model_is_unchanged_until_explicit_migration(tmp_path):
    old = Model.from_data(
        dict(metadata=dict(id=str(UUID(int=1)), schema_version="0.7.0"))
    )
    migrated = model_07_to_08(old, id=UUID(int=2))
    assert migrated.metadata.previous == old.id
    assert old.metadata.schema_version == "0.7.0"
    assert migrated.metadata.schema_version == "0.8.0"
    write(tmp_path / "old", old)
    write(tmp_path / "new", migrated)
    assert Reader(tmp_path / "old").model().to_data() == old.to_data()
    assert identity(old) != identity(migrated)
