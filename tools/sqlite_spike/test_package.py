"""Lossless storage, incomplete assets, identity and read-boundary checks."""

import json
from pathlib import Path
import sqlite3

import pytest
import yaml

from package import build, capture_inputs, encoded, Reader, sha
from render_probe import area, triangulate
from fixtures import fixture, uid


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def package(tmp_path):
    path = tmp_path / "probe.rk.sqlite"
    build(path, *fixture())
    return path


def test_roundtrip_and_field_presence(package):
    with Reader(package) as reader:
        assert encoded(reader.model().to_data()) == encoded(json.loads(fixture()[0]))
        assert "name" not in reader.object(uid("a"))
        assert reader.object(uid("b"))["name"] is None
        assert reader.object(uid("b"))["characteristics"]["values"] == []
        assert "content" not in reader.object(uid("unresolved"))
        assert reader.object(uid("null"))["content"] == {"kind": "null"}
        assert reader.object(uid("false"))["content"]["text"] == "False"
        assert encoded(reader.object(uid("zero"))["quantity"]["magnitude"]) == "-0.0"
        assert reader.object(uid("claim"))["content"]["id"] == uid("a")
        assert len(reader.members(uid("shared"))) == 1
        reader.verify()


def test_queries_do_not_read_geometry_or_retained_document(package):
    reads = []

    def authorizer(action, table, column, database, trigger):
        if action == sqlite3.SQLITE_READ:
            reads.append((table, column))
            if table in ("geometry", "documents"):
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    with Reader(package) as reader:
        reader.db.set_authorizer(authorizer)
        assert len(reader.objects(limit=2)) == 2
        assert len(reader.members(uid("assembly"))) == 3
        assert reader.object(uid("a"))["id"] == uid("a")
    assert reads


def test_rendering_does_not_change_model(package):
    before = sha(package.read_bytes())
    with Reader(package) as reader:
        mesh = json.loads(reader.geometry_object("quad"))
        a, b = triangulate(mesh, "02"), triangulate(mesh, "13")
        assert a["triangles"] != b["triangles"]
        assert a["cache_key"] != b["cache_key"]
        assert a["vertices"] == b["vertices"]
        assert area(a) == area(b) == 4
        assert reader.metadata["model_id"] == uid("model")
    assert before == sha(package.read_bytes())


def test_read_only_and_no_overwrite(package):
    before = sha(package.read_bytes())
    with Reader(package) as reader:
        with pytest.raises(sqlite3.OperationalError):
            reader.db.execute("DELETE FROM geometry")
    with pytest.raises(FileExistsError):
        build(package, *fixture())
    assert before == sha(package.read_bytes())


@pytest.mark.parametrize("error", ["missing", "association", "revision", "external"])
def test_invalid_geometry_is_not_published(tmp_path, error):
    model, transport, associations, descriptor = fixture()
    if error == "missing":
        mesh = json.loads(transport["quad"])
        mesh["vertices"] = [{"speckle_type": "reference", "referencedId": "missing"}]
        transport["quad"] = encoded(mesh)
    elif error == "association":
        associations[0]["domain_id"] = uid("not-in-model")
    elif error == "revision":
        associations[0]["model_revision"] = uid("another-model")
    else:
        mesh = json.loads(transport["quad"])
        mesh["textureUrl"] = "https://example.invalid/texture.png"
        transport["quad"] = encoded(mesh)
    target = tmp_path / "invalid.rk.sqlite"
    messages = {
        "missing": "missing geometry dependencies",
        "association": "not-in-model|[0-9a-f]{8}-",
        "revision": "another Model revision",
        "external": "unsupported external geometry asset",
    }
    with pytest.raises(ValueError, match=messages[error]):
        build(target, model, transport, associations, descriptor)
    assert not target.exists()
    assert not list(tmp_path.glob(".rk-sqlite-*"))


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM refs",
        "DELETE FROM geometry",
        "UPDATE geometry SET data=x'0000'",
        "UPDATE associations SET geometry_id='missing'",
        "DELETE FROM children",
        "UPDATE rk_Entity SET name='\"tampered\"'",
        "DELETE FROM records WHERE kind='Claim'",
    ],
)
def test_corruption_is_detected(package, statement):
    with sqlite3.connect(package) as db:
        db.execute(statement)
    with Reader(package) as reader:
        with pytest.raises(ValueError):
            reader.verify()


def test_content_digest_separates_geometry_from_legacy_model_id(tmp_path):
    args = fixture()
    first = build(tmp_path / "a.sqlite", *args)
    changed = json.loads(args[1]["quad"])
    changed["vertices"][3] = 3
    args[1]["quad"] = encoded(changed)
    second = build(tmp_path / "b.sqlite", *args)
    assert (
        first["model_id"] == second["model_id"]
    )  # Current public schema excludes geometry.
    assert first["model_digest"] == second["model_digest"]
    assert first["content_digest"] != second["content_digest"]


def test_physical_index_does_not_change_content_identity(package):
    before = sha(package.read_bytes())
    with Reader(package) as reader:
        identity = reader.metadata["content_digest"]
    with sqlite3.connect(package) as db:
        db.execute("CREATE INDEX extra_probe_index ON records(kind,path)")
    assert sha(package.read_bytes()) != before
    with Reader(package) as reader:
        assert reader.verify()["content_digest"] == identity


def test_repeat_export_has_same_content_digest(tmp_path):
    a = build(tmp_path / "a.sqlite", *fixture())
    b = build(tmp_path / "b.sqlite", *fixture())
    assert a["content_digest"] == b["content_digest"]


def test_real_capture(tmp_path):
    target = tmp_path / "real.sqlite"
    args = capture_inputs(ROOT / "examples/data/mixed_use_property")
    build(target, *args)
    with Reader(target) as reader:
        result = reader.verify()
        assert result["geometry_records"] == 3007
        assert encoded(reader.model().to_data()) == encoded(json.loads(args[0]))
        for identity, text in args[1].items():
            assert reader.geometry_object(identity) == text
    assert {p.name for p in tmp_path.iterdir()} == {"real.sqlite"}


@pytest.mark.parametrize(
    "name", ["model.yaml", "model-forward-output.yaml", "model-inverse-output.yaml"]
)
def test_formulations_without_geometry(tmp_path, name):
    data = yaml.safe_load((ROOT / "examples/schema" / name).read_text())
    path = tmp_path / "model.sqlite"
    build(path, json.dumps(data))
    with Reader(path) as reader:
        assert encoded(reader.model().to_data()) == encoded(data)
        assert reader.verify()["geometry_records"] == 0


@pytest.mark.parametrize("limit,offset", [(0, 0), (201, 0), (True, 0), (2, -1)])
def test_page_bounds(package, limit, offset):
    with Reader(package) as reader, pytest.raises(ValueError):
        reader.objects(limit=limit, offset=offset)


def test_new_model_schema_is_rejected_before_publication(tmp_path):
    model = json.loads(fixture()[0])
    model["metadata"]["schema_version"] = "0.8.0"
    target = tmp_path / "new-model.rk.sqlite"
    with pytest.raises(ValueError, match="requires Model schema 0.7.0"):
        build(target, json.dumps(model))
    assert not target.exists()
    assert not list(tmp_path.glob(".rk-sqlite-*"))
