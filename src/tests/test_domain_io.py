"""Codec fidelity and atomic immutable revision publication at public IO boundaries."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json as stdjson
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier
from uuid import uuid4

import pytest
import yaml as pyyaml

import rangekeeper as rk
from rangekeeper.io import json, yaml, MemoryStore, DirectoryStore
from rangekeeper.model import Metadata, System, Entity, Update
from rangekeeper.errors import (
    DecodeError,
    ValidationError,
    RevisionConflictError,
    MissingReferenceError,
    ReferenceTypeError,
    IdentityConflictError,
    UnsupportedVersionError,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "schema/examples"
FIXTURES = sorted(
    p
    for p in EXAMPLES.glob("*.yaml")
    if p.stem.startswith(("model", "specification", "run"))
)


def minimal():
    return rk.Model.create(metadata=Metadata(id=uuid4(), schema_version="0.4.0"))


@pytest.fixture(params=["memory", "directory"])
def store(request, tmp_path):
    return (
        MemoryStore()
        if request.param == "memory"
        else DirectoryStore(tmp_path / "records")
    )


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
@pytest.mark.parametrize("codec", [json, yaml], ids=["json", "yaml"])
def test_every_fixture_roundtrips_without_storage_envelopes(path, codec):
    kind = getattr(rk, path.stem.split("-")[0].capitalize())
    data = pyyaml.safe_load(path.read_text())
    document = kind.from_data(data)
    text = codec.dumps(document)
    assert codec.loads(text, kind=kind).to_data() == document.to_data()
    assert "document" not in pyyaml.safe_load(text)  # report references remain nested


@pytest.mark.parametrize(
    "codec,text",
    [
        (json, '{"metadata": {}, "metadata": {}}'),
        (json, '{"nested": {"x": 1, "x": 2}}'),
        (json, '{"value": NaN}'),
        (json, '{"value": 1e999}'),
        (yaml, "metadata: {}\nmetadata: {}"),
        (yaml, "nested: {x: 1, x: 2}"),
        (yaml, "value: .nan"),
        (yaml, "value: !!bool invalid"),
        (yaml, "value: .inf"),
        (yaml, "value: &a [*a]"),
        (yaml, 'value: !!python/object/apply:os.system ["false"]'),
        (yaml, "value: !!binary YQ=="),
        (yaml, "value: !!set {a: null}"),
        (yaml, "value: {<<: {x: 1}, x: 2}"),
        (yaml, "1: value"),
        (yaml, "---\n{}\n---\n{}"),
    ],
)
def test_ambiguous_or_non_json_text_is_rejected(codec, text):
    with pytest.raises(DecodeError):
        codec.loads(text, kind=rk.Model)


@pytest.mark.parametrize("codec", [json, yaml])
def test_codecs_require_kind_and_distinguish_decode_shape_and_version_errors(codec):
    with pytest.raises(TypeError):
        codec.loads("{}", kind=dict)
    with pytest.raises(ValidationError):
        codec.loads("{}", kind=rk.Model)
    data = minimal().to_data()
    data["metadata"]["schema_version"] = "999"
    with pytest.raises(UnsupportedVersionError):
        codec.loads(stdjson.dumps(data), kind=rk.Model)


def test_yaml_preserves_json_scalar_meaning_inside_opaque_claims():
    data = pyyaml.safe_load((EXAMPLES / "model.yaml").read_text())
    opaque = {
        "id": str(uuid4()).upper(),
        "date": "2026-10-02",
        "at": "2026-10-02T00:00:00Z",
        "false": False,
        "zero": 0,
        "float": 0.0,
        "null": None,
        "empty": [],
        "order": [2, 1],
        "on": "on",
    }
    data["provenance"]["claims"][0]["content"] = opaque
    document = rk.Model.from_data(data)
    restored = yaml.loads(yaml.dumps(document), kind=rk.Model)
    assert stdjson.dumps(restored.to_data()) == stdjson.dumps(document.to_data())
    assert restored.to_data()["provenance"]["claims"][0]["content"] == opaque
    # Timestamp-looking scalars remain strings even when supplied without quotes.
    text = (
        yaml.dumps(document)
        .replace("'2026-10-02'", "2026-10-02")
        .replace("'2026-10-02T00:00:00Z'", "2026-10-02T00:00:00Z")
    )
    assert yaml.loads(text, kind=rk.Model).to_data() == document.to_data()


@pytest.mark.parametrize("codec", [json, yaml])
def test_file_codec_never_overwrites_and_preserves_existing_bytes(codec, tmp_path):
    path = tmp_path / "document.txt"
    document = minimal()
    assert codec.write(document, path) == path
    original = path.read_bytes()
    assert codec.read(path, kind=rk.Model).id == document.id
    with pytest.raises(FileExistsError):
        codec.write(document, path)
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]
    path.write_bytes(b"\xff")
    with pytest.raises(DecodeError):
        codec.read(path, kind=rk.Model)


def test_store_pins_snapshots_and_preserves_old_revisions(store):
    before = minimal()
    store.put(before)
    after = before.revise(
        Update(system=System(entities=(Entity(id=uuid4(), code="A"),)))
    )
    store.put(after)
    assert store.load_model(before.id).to_data() == before.to_data()
    assert store.load_model(after.id).metadata.previous == before.id
    detached = store.load_model(after.id).to_data()
    detached["system"].clear()
    assert store.load_model(after.id).system.entities
    assert store.put(before) == before.id
    with pytest.raises(MissingReferenceError):
        store.load_model(uuid4())
    with pytest.raises(ReferenceTypeError):
        store.load_run(before.id)
    with pytest.raises(TypeError):
        store.load_model(str(before.id))


def test_conflicting_content_and_kind_do_not_replace_a_revision(store):
    document = minimal()
    store.put(document)
    data = document.to_data()
    data["metadata"]["name"] = "different"
    with pytest.raises(RevisionConflictError):
        store.put(rk.Model.from_data(data))
    spec = rk.Specification.from_data(
        {"metadata": {"id": str(document.id), "schema_version": "0.4.0"}}
    )
    with pytest.raises(RevisionConflictError):
        store.put(spec)
    assert store.load_model(document.id).to_data() == document.to_data()


def test_unordered_equivalence_keeps_first_encounter_order(store):
    data = minimal().to_data()
    data["system"] = {
        "entities": [
            {"id": str(uuid4()), "code": "A"},
            {"id": str(uuid4()), "code": "B"},
        ]
    }
    original = rk.Model.from_data(data)
    store.put(original)
    data["system"]["entities"].reverse()
    data["metadata"]["id"] = data["metadata"]["id"].upper()
    store.put(rk.Model.from_data(data))
    assert store.load_model(original.id).to_data() == original.to_data()


@pytest.mark.parametrize("change", ["number", "bool", "order", "presence"])
def test_revision_equivalence_preserves_opaque_representations(store, change):
    data = minimal().to_data()
    data["provenance"] = {
        "claims": [
            {
                "id": str(uuid4()),
                "kind": "asserted",
                "method": {"code": "manual"},
                "content": {"value": 0, "items": [1, 2]},
            }
        ]
    }
    first = rk.Model.from_data(data)
    store.put(first)
    content = data["provenance"]["claims"][0]["content"]
    if change == "number":
        content["value"] = 0.0
    elif change == "bool":
        content["value"] = False
    elif change == "order":
        content["items"].reverse()
    else:
        content["extra"] = None
    with pytest.raises(RevisionConflictError):
        store.put(rk.Model.from_data(data))


def test_model_mathematical_order_is_not_canonicalized_away(store):
    data = pyyaml.safe_load((EXAMPLES / "model.yaml").read_text())
    # Add valid unused arithmetic so reversal remains semantically valid but differs.
    data.setdefault("system", {}).setdefault("formulations", []).append(
        {
            "id": str(uuid4()),
            "expressions": [
                {
                    "id": str(uuid4()),
                    "kind": "binary",
                    "operator": "subtract",
                    "operands": [
                        {
                            "id": str(uuid4()),
                            "kind": "quantity",
                            "quantity": {"magnitude": x, "units": "dimensionless"},
                        }
                        for x in (2, 1)
                    ],
                }
            ],
        }
    )
    original = rk.Model.from_data(data)
    store.put(original)
    data["system"]["formulations"][-1]["expressions"][0]["operands"].reverse()
    with pytest.raises(RevisionConflictError):
        store.put(rk.Model.from_data(data))


def test_directory_construction_and_invalid_put_do_not_create_storage(tmp_path):
    root = tmp_path / "absent"
    store = DirectoryStore(root)
    assert not root.exists()
    run = rk.Run.from_data(
        pyyaml.safe_load((EXAMPLES / "run-forward.yaml").read_text())
    )
    with pytest.raises(ValidationError):
        store.put(run)
    assert not root.exists()


@pytest.mark.parametrize(
    "change,error",
    [
        ("identity", IdentityConflictError),
        ("kind", DecodeError),
        ("envelope", DecodeError),
        ("version", UnsupportedVersionError),
    ],
)
def test_directory_reads_verify_envelope_identity_kind_and_version(
    tmp_path, change, error
):
    store = DirectoryStore(tmp_path)
    document = minimal()
    store.put(document)
    path = tmp_path / f"{document.id}.json"
    data = stdjson.loads(path.read_text())
    if change == "identity":
        data["document"]["metadata"]["id"] = str(uuid4())
    elif change == "kind":
        data["kind"] = "Graph"
    elif change == "envelope":
        data["extra"] = True
    else:
        data["document"]["metadata"]["schema_version"] = "999"
    path.write_text(stdjson.dumps(data))
    with pytest.raises(error):
        store.load_model(document.id)


@pytest.mark.parametrize("same", [True, False])
def test_concurrent_directory_puts_are_idempotent_or_conflicting(
    tmp_path, monkeypatch, same
):
    from rangekeeper.io import _atomic

    barrier = Barrier(2)
    real_link = os.link

    def link(source, target):
        barrier.wait(timeout=10)
        return real_link(source, target)

    monkeypatch.setattr(_atomic.os, "link", link)
    first = minimal()
    data = first.to_data()
    if not same:
        data["metadata"]["name"] = "competitor"
    second = rk.Model.from_data(data)

    def publish(document):
        try:
            return DirectoryStore(tmp_path).put(document)
        except RevisionConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(publish, (first, second)))
    assert results.count(first.id) == (2 if same else 1)
    assert results.count("conflict") == (0 if same else 1)
    assert len(list(tmp_path.iterdir())) == 1


def test_interrupted_publication_exposes_no_partial_final_file(tmp_path, monkeypatch):
    from rangekeeper.io import _atomic

    real_link = os.link

    def fail(source, target):
        raise OSError("interrupted before link")

    monkeypatch.setattr(_atomic.os, "link", fail)
    document = minimal()
    store = DirectoryStore(tmp_path)
    with pytest.raises(OSError, match="interrupted"):
        store.put(document)
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(_atomic.os, "link", real_link)
    store.put(document)
    assert store.load_model(document.id).id == document.id


def test_process_crash_before_link_leaves_only_ignored_temporary_file(tmp_path):
    script = """
import os, sys
from pathlib import Path
from uuid import UUID
from rangekeeper import Model
from rangekeeper.model import Metadata
from rangekeeper.io import DirectoryStore, _atomic
_atomic.os.link = lambda *args: os._exit(23)
DirectoryStore(Path(sys.argv[1])).put(Model.create(metadata=Metadata(id=UUID(sys.argv[2]), schema_version="0.4.0")))
"""
    identity = uuid4()
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), str(identity)]
    )
    assert result.returncode == 23
    assert not (tmp_path / f"{identity}.json").exists()
    assert all(p.suffix == ".tmp" for p in tmp_path.iterdir())
    store = DirectoryStore(tmp_path)
    with pytest.raises(MissingReferenceError):
        store.load_model(identity)
    document = rk.Model.create(metadata=Metadata(id=identity, schema_version="0.4.0"))
    store.put(document)
    assert store.load_model(identity).id == identity


def test_store_preserves_objective_order(store):
    data = pyyaml.safe_load((EXAMPLES / "specification-objectives.yaml").read_text())
    assert len(data["objectives"]) > 1
    store.put(rk.Specification.from_data(data))
    data["objectives"].reverse()
    with pytest.raises(RevisionConflictError):
        store.put(rk.Specification.from_data(data))


def test_store_preserves_trace_order_and_optional_presence(store):
    spec = rk.Specification.from_data(
        {"metadata": {"id": str(uuid4()), "schema_version": "0.4.0"}}
    )
    store.put(spec)
    data = {
        "metadata": {"id": str(uuid4()), "schema_version": "0.1.0"},
        "specification": str(spec.id),
        "report": {
            "status": {"completion": "failed", "solution": "not_assessed"},
            "diagnostics": [
                {
                    "severity": "error",
                    "code": "specification_invalid",
                    "message": "Incomplete investigation",
                }
            ],
            "trace": [
                {"kind": "validation", "message": name} for name in ("first", "second")
            ],
        },
    }
    store.put(rk.Run.from_data(data))
    reversed_trace = deepcopy(data)
    reversed_trace["report"]["trace"].reverse()
    with pytest.raises(RevisionConflictError):
        store.put(rk.Run.from_data(reversed_trace))
    data["outputs"] = None
    with pytest.raises(RevisionConflictError):
        store.put(rk.Run.from_data(data))


def test_codec_preserves_permission_errors(tmp_path, monkeypatch):
    from rangekeeper.io import _atomic

    def denied(*args, **kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(_atomic.tempfile, "mkstemp", denied)
    with pytest.raises(PermissionError):
        json.write(minimal(), tmp_path / "file.json")
    assert list(tmp_path.iterdir()) == []
