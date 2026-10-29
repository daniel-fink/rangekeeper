"""Standalone schema/Parquet conformance without a source service."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
import yaml

pytest.importorskip("pyarrow")
from rangekeeper import Model
from rangekeeper.errors import ContractError
from rangekeeper.io.bundle import (
    GeometrySources,
    IndexCheck,
    ParquetOptions,
    Reader,
    ReadLimits,
    model_digest,
    write,
)
from rangekeeper.schema.runtime import exact_equal

ROOT = Path(__file__).parents[2]


def test_record_query_filters_in_parquet_without_arrow_materialization(
    tmp_path, monkeypatch
):
    import pyarrow.parquet as pq

    model = Model.from_data(
        dict(
            metadata=dict(id=str(UUID(int=1)), schema_version="1.0.0"),
            system=dict(
                entities=[
                    dict(id=str(UUID(int=i)), name=f"Entity {i}")
                    for i in range(2, 1002)
                ]
            ),
        )
    )
    write(tmp_path / "bundle", model, parquet=ParquetOptions(row_group_size=64))
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


def test_lineage_slots_are_not_model_references():
    from rangekeeper.io.bundle import _shred

    data = yaml.safe_load((ROOT / "examples/schema/model.yaml").read_text())
    data["metadata"]["previous"] = str(UUID(int=1))
    _, _, references = _shred(Model.from_data(data))
    assert references
    assert not [r for r in references if r["path"] == "/metadata"]


def test_records_page_in_numeric_path_order(tmp_path):
    model = Model.from_data(
        dict(
            metadata=dict(id=str(UUID(int=1)), schema_version="1.0.0"),
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
    reader = Reader(root, index=IndexCheck.SCHEMA)
    assert exact_equal(reader.model().to_data(), model.to_data())
    damaged = index.read_bytes()
    index.write_bytes(damaged[:-1] + bytes([damaged[-1] ^ 1]))
    with pytest.raises(ValueError):
        Reader(root, index=IndexCheck.SCHEMA)


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
    write(tmp_path / "bundle", model, parquet=ParquetOptions(row_group_size=1))
    assert exact_equal(Reader(tmp_path / "bundle").model().to_data(), before)
    reordered = deepcopy(before)
    for name in ("entities", "relationships", "assemblies"):
        if name in reordered.get("system", {}):
            reordered["system"][name].reverse()
    assert model_digest(Model.from_data(reordered)) == model_digest(model)


def test_unknown_format_unsafe_inventory_and_limits(tmp_path):
    import json

    model = Model.from_data(
        dict(metadata=dict(id=str(UUID(int=1)), schema_version="1.0.0"))
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
        Reader(tmp_path / "bundle", limits=ReadLimits(rows=1))


@pytest.mark.parametrize(
    ("make", "error"),
    [
        (lambda: ParquetOptions(compression="zip"), ContractError),
        (lambda: ParquetOptions(row_group_size=0), ContractError),
        (lambda: ParquetOptions(row_group_size="1"), TypeError),
        (lambda: ReadLimits(rows=0), ContractError),
        (lambda: ReadLimits(documents=True), TypeError),
        (lambda: GeometrySources(directories={"model": Path(".")}), TypeError),
        (lambda: GeometrySources(providers={("a", "b", "1"): object()}), TypeError),
    ],
)
def test_options_reject_a_wrong_type_or_value(make, error):
    with pytest.raises(error):
        make()


def test_the_index_check_is_an_index_check(tmp_path):
    model = Model.from_data(
        dict(metadata=dict(id=str(UUID(int=1)), schema_version="1.0.0"))
    )
    write(tmp_path / "bundle", model)
    with pytest.raises(TypeError, match="IndexCheck"):
        Reader(tmp_path / "bundle", index=False)


class _Provider:
    """A Geometry provider that requires each pinned file and records each check."""

    def __init__(self):
        self.checked = []

    def validate(self, path, geometry):
        for entry in geometry.pin.files:
            assert (path / entry.path).read_bytes()
        self.checked.append(path)


def _spatial_model(source):
    from rangekeeper.model.geometry import inventory_digest

    (source / "parts").mkdir(parents=True)
    (source / "parts/a.dat").write_bytes(b"native geometry")
    content = (source / "parts/a.dat").read_bytes()
    files = [
        dict(path="parts/a.dat", sha256=sha256(content).hexdigest(), size=len(content))
    ]
    pin = dict(
        provider="synthetic",
        format="test-format",
        format_version="1",
        specification="urn:synthetic:test:1",
        specification_digest="1" * 64,
        content_digest=inventory_digest(files),
        files=files,
    )
    return Model.from_data(
        dict(
            metadata=dict(id=str(UUID(int=1)), schema_version="1.0.0"),
            geometry=dict(pin=pin),
        )
    )


def test_geometry_files_are_copied_and_checked_by_their_provider(tmp_path):
    model = _spatial_model(tmp_path / "source")
    provider = _Provider()
    key = ("synthetic", "test-format", "1")
    sources = GeometrySources(
        directories={model.id: tmp_path / "source"}, providers={key: provider}
    )
    manifest = write(tmp_path / "bundle", model, geometry=sources)
    assert manifest["geometry_paths"] == {str(model.id): "geometry"}
    # The source, the copy, and the copy again when write reads the Bundle back.
    assert len(provider.checked) == 3
    reader = Reader(tmp_path / "bundle", providers={key: provider})
    assert reader.geometry_path() == reader.root / "geometry"
    reader.verify_geometry()
    assert provider.checked[-1] == reader.root / "geometry"
    with pytest.raises(ValueError, match="explicit provider"):
        Reader(tmp_path / "bundle").verify_geometry()


def test_geometry_needs_its_files_and_a_provider(tmp_path):
    model = _spatial_model(tmp_path / "source")
    key = ("synthetic", "test-format", "1")
    with pytest.raises(ValueError, match="native files"):
        write(
            tmp_path / "none",
            model,
            geometry=GeometrySources(providers={key: _Provider()}),
        )
    with pytest.raises(ValueError, match="explicit provider"):
        write(
            tmp_path / "unchecked",
            model,
            geometry=GeometrySources(directories={model.id: tmp_path / "source"}),
        )
    other = UUID(int=2)
    with pytest.raises(ValueError, match="no declared Model pin"):
        write(
            tmp_path / "unknown",
            model,
            geometry=GeometrySources(directories={other: tmp_path / "source"}),
        )
