"""Synthetic transport evidence; no credentials or real design payloads."""

from copy import deepcopy
from uuid import uuid4
import pytest
from rangekeeper.adapters.speckle import decode_model, encode_model, MappingError
from rangekeeper.migration.speckle import MappingSpec, convert_speckle
from rangekeeper.model.characteristics import value
from rangekeeper.model.content import decode
from rangekeeper.io import json as codec


def payload():
    node = {
        "entityId": str(uuid4()),
        "speckle_type": "Rangekeeper.Entity",
        "type": "room",
        "name": "Shared room",
        "area": 0,
        "description": {"available": False},
        "id": "speckle-a",
    }
    root = {
        "entityId": str(uuid4()),
        "speckle_type": "Rangekeeper.Assembly",
        "type": "building",
        "name": "Root",
        "relationships": [{"source": None, "target": node, "type": "contains"}],
    }
    return {"collection": [root, deepcopy(node)]}, root, node


def spec():
    return MappingSpec(
        classifications=("room", "building"),
        relationships=("contains",),
        measurements={"area": "meter ** 2"},
        properties=("description",),
    )


def test_explicit_legacy_conversion_keeps_shared_identity_and_missingness():
    data, root, node = payload()
    original = deepcopy(data)
    result = convert_speckle(data, mapping=spec())
    assert result.model, result.issues
    model = result.model
    assert len(model.find_entities()) == 2 and len(model.system.relationships) == 1
    owner = model.entity(__import__("uuid").UUID(node["entityId"]))
    assert value(owner.characteristics, "area").quantity.magnitude == 0
    assert decode(value(owner.characteristics, "description").content) == {
        "available": False
    }
    assert len(model.system.assemblies[0].entities) == 1
    assert data == original
    assert (
        model.provenance.facts
        and model.provenance.sources[0].checksum == result.source_sha256
    )
    envelope = encode_model(model, associations=result.associations)
    assert decode_model(envelope).to_data() == model.to_data()
    assert len(result.associations) == 1


@pytest.mark.parametrize(
    "change", ["conflict", "unknown", "missing", "invalid", "name_identity"]
)
def test_conversion_reports_path_and_never_returns_partial_model(change):
    data, root, node = payload()
    if change == "conflict":
        data["collection"][1]["area"] = 1
    elif change == "unknown":
        node["unsupported"] = 1
    elif change == "missing":
        root["relationships"][0]["target"] = str(uuid4())
    elif change == "invalid":
        node["entityId"] = "same name is not an identity"
    else:
        data["collection"][1]["entityId"] = node["name"]
    result = convert_speckle(data, mapping=spec())
    assert result.model is None and result.issues
    assert "/" in result.issues[0]


def test_entity_assembly_duplicate_requires_matching_shared_content():
    data, root, node = payload()
    copy = deepcopy(root)
    copy["speckle_type"] = "Rangekeeper.Entity"
    copy["relationships"] = []
    data["collection"].append(copy)
    result = convert_speckle(data, mapping=spec())
    assert result.model, result.issues
    copy["name"] = "Conflict"
    failed = convert_speckle(data, mapping=spec())
    assert not failed.model
    assert root["entityId"] in failed.issues[0]


def test_canonical_envelope_rejects_legacy_wrong_revision_and_invalid_json():
    data, _, _ = payload()
    with pytest.raises(MappingError, match="convert_speckle"):
        decode_model(data)
    result = convert_speckle(data, mapping=spec())
    envelope = encode_model(result.model, associations=result.associations)
    envelope["rk_associations"][0]["model_revision"] = str(uuid4())
    with pytest.raises(MappingError, match="revision"):
        decode_model(envelope)
    envelope["rk_model"] = '{"bad":1,"bad":2}'
    with pytest.raises(MappingError):
        decode_model(envelope)


def test_conversion_retains_null_property_and_unresolved_quantity():
    data, _, node = payload()
    node["area"] = None
    node["description"] = None
    data["collection"][1] = deepcopy(node)
    result = convert_speckle(data, mapping=spec())
    assert result.model, result.issues
    owner = result.model.system.entities[0]
    assert value(owner.characteristics, "area").quantity is None
    assert decode(value(owner.characteristics, "description").content) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("domain_id", str(uuid4())),
        ("rhino_id", "invalid"),
        ("application_id", ""),
        ("content_id", 0),
        ("unsupported", False),
    ],
)
def test_association_errors_identify_the_source_path(field, value):
    data, _, _ = payload()
    converted = convert_speckle(data, mapping=spec())
    envelope = encode_model(converted.model, associations=converted.associations)
    envelope["rk_associations"][0][field] = value
    with pytest.raises(MappingError, match="/rk_associations/0"):
        decode_model(envelope)


def test_transport_is_pinned_detached_and_read_only(monkeypatch):
    """Use an SDK stand-in so this test needs no SDK or service account."""
    import sys
    from types import SimpleNamespace
    from rangekeeper.adapters.speckle import transport

    calls = []
    raw = {"content": {"zero": 0, "false": False, "null": None}}
    client = SimpleNamespace(
        version=SimpleNamespace(
            get=lambda version_id, project_id: SimpleNamespace(
                referenced_object="pinned-content"
            )
        )
    )

    def receive(**kwargs):
        calls.append(kwargs)
        return raw

    monkeypatch.setitem(
        sys.modules,
        "specklepy.api",
        SimpleNamespace(operations=SimpleNamespace(receive=receive)),
    )
    monkeypatch.setitem(
        sys.modules,
        "specklepy.transports.server",
        SimpleNamespace(ServerTransport=lambda **kwargs: kwargs),
    )
    monkeypatch.setattr(transport, "version", lambda name: "test-sdk")
    result = transport.receive(client, project_id="project", version_id="version")
    assert calls[0]["obj_id"] == "pinned-content"
    assert result.source["version_id"] == "version"
    assert result.source["sdk_version"] == "test-sdk"
    client.version.get = lambda *args: SimpleNamespace(referenced_object=None)
    with pytest.raises(transport.TransportError, match="no readable object reference"):
        transport.receive(client, project_id="project", version_id="hidden-version")
    assert len(calls) == 1  # A hidden version must not trigger an object fetch.
    raw["content"]["zero"] = 12
    assert result.payload["content"]["zero"] == 0
    with pytest.raises(TypeError):
        result.payload["content"]["zero"] = 1
    with pytest.raises(ValueError, match="exactly one"):
        transport.receive(client, project_id="project")
    with pytest.raises(ValueError, match="exactly one"):
        transport.receive(client, project_id="project", version_id="v", object_id="o")
