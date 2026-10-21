"""Exact public locations preserve the exhaustive walk without repeating its work."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import yaml

from rangekeeper.model import Entity, Metadata, Model, Quantity, System, Update
from rangekeeper.model.content import encode
import rangekeeper.schema.index as index_module
import rangekeeper.schema.records as records_module
from rangekeeper.schema.index import RecordIndex, RecordLocation, walk
from rangekeeper.schema.records import Model as ModelRecord
from rangekeeper.schema.runtime import Record
from rangekeeper.schema.validation import _slot_map
from rangekeeper.shared.errors import MissingReferenceError


@pytest.fixture(scope="module")
def inspected():
    data = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "examples/schema/model.yaml").read_text()
    )
    values = data["system"]["entities"][0]["characteristics"]["values"]
    values.append(
        dict(
            id=str(UUID(int=10000)),
            key="inspection-property",
            kind="property",
            content=encode({"a/b~c": [None, False, 0, {"nested": "value"}]}).to_data(),
        )
    )
    data["provenance"]["claims"][0]["content"]["id"] = str(UUID(int=10001))
    data["provenance"]["claims"][0]["content"]["system"] = {
        "entities": [{"id": str(UUID(int=10002))}]
    }
    # Construct the exhaustive oracle independently through the public record API.
    model = Model.from_data(data)
    oracle = tuple(walk(ModelRecord.from_data(data)))
    return model, oracle


def assert_location(location, record, owner, path):
    assert isinstance(location, RecordLocation)
    assert type(location.record) is type(record)
    assert location.record == record
    assert location.record.to_data() == record.to_data()
    assert location.owner_id == owner
    assert location.path == path
    assert location.record.field_names() == record.field_names()


def test_every_path_and_identity_matches_independent_exhaustive_walk(inspected):
    model, oracle = inspected
    before = model.to_data()
    kinds = set()
    for record, owner, path in oracle:
        kinds.add(type(record).__name__)
        assert_location(model.record_at(path), record, owner, path)
        if "id" in _slot_map(record._kind):
            assert_location(model.record_by_id(record.id), record, owner, path)
    assert {
        "Model",
        "Metadata",
        "Characteristics",
        "Quantity",
        "Location",
        "Method",
        "PropertyContent",
        "ContentEntry",
    } <= kinds
    assert model.to_data() == before


def test_revision_identity_selects_metadata_and_root_remains_anonymous(inspected):
    model, _ = inspected
    root = model.record_at("")
    metadata = model.record_by_id(model.id)
    assert type(root.record) is ModelRecord
    assert root.owner_id is None and root.path == ""
    assert metadata.record == model.metadata
    assert metadata.owner_id is None and metadata.path == "/metadata"


def test_nearest_owner_is_preserved_through_anonymous_containers(inspected):
    model, oracle = inspected
    for kind in (
        "Characteristics",
        "Quantity",
        "Location",
        "Method",
        "PropertyContent",
    ):
        record, owner, path = next(
            row for row in oracle if type(row[0]).__name__ == kind
        )
        assert owner is not None
        assert_location(model.record_at(path), record, owner, path)
    entity_path = "/system/entities/0"
    entity = model.record_at(entity_path)
    assert entity.owner_id is None
    assert (
        model.record_at(entity_path + "/characteristics").owner_id == entity.record.id
    )


@pytest.mark.parametrize("path", [None, 1, False, UUID(int=1), [], {}])
def test_path_requires_string(inspected, path):
    with pytest.raises(TypeError):
        inspected[0].record_at(path)


@pytest.mark.parametrize(
    "identity", [None, 1, False, "00000000-0000-0000-0000-000000000001"]
)
def test_identity_requires_uuid(inspected, identity):
    with pytest.raises(TypeError):
        inspected[0].record_by_id(identity)


@pytest.mark.parametrize(
    "path",
    [
        "metadata",
        "#/metadata",
        " /metadata",
        "/metadata/~",
        "/metadata/~2",
        "/metadata/~00~",
        "/system/entities/-1",
        "/system/entities/+1",
        "/system/entities/00",
        "/system/entities/01",
        "/system/entities/-",
        "/system/entities/1.0",
        "/system/entities/ 0",
        "/system/entities/٠",
        "/system/entities/0x0",
        "/system/entities/",
    ],
)
def test_malformed_pointers_and_array_aliases_are_argument_errors(inspected, path):
    with pytest.raises(ValueError):
        inspected[0].record_at(path)


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "//metadata",
        "/unknown",
        "/metadata/name",
        "/metadata/id",
        "/metadata/previous",
        "/metadata/~0",
        "/metadata/~1",
        "/metadata~1name",
        "/system/entities",
        "/system/entities/999",
        "/system/entities/" + "9" * 5000,
        "/system/entities/0/name",
        "/system/entities/0/id",
        "/system/entities/0/unknown",
        "/provenance/claims/0/content",
        "/provenance/claims/0/content/id",
        "/provenance/claims/0/content/system/entities/0",
        "/provenance/claims/0/sources/0/source",
        "/provenance/claims/0/sources/0/address",
        "/provenance/claims/0/sources/0/address/line",
        "/provenance/claims/2/sources/0",
        "/provenance/claims/2/sources/0/method",
    ],
)
def test_non_record_and_missing_locations_use_missing_reference(inspected, path):
    with pytest.raises(MissingReferenceError):
        inspected[0].record_at(path)


def test_opaque_identity_is_not_a_declaration(inspected):
    model, _ = inspected
    for identity in (UUID(int=10001), UUID(int=10002), uuid4()):
        with pytest.raises(MissingReferenceError):
            model.record_by_id(identity)


@pytest.mark.parametrize("system", [{}, {"entities": None}, {"entities": []}])
def test_null_and_empty_record_containers_remain_distinct(system):
    data = dict(metadata=dict(id=str(uuid4()), schema_version="0.8.0"), system=system)
    model = Model.from_data(data)
    root = model.record_at("").record
    assert root.has_field("system")
    assert root.to_data()["system"] == system
    assert model.record_at("/system").record.to_data() == system
    with pytest.raises(MissingReferenceError):
        model.record_at("/system/entities/0")


def test_null_record_field_is_not_synthesized():
    model = Model.from_data(
        dict(
            metadata=dict(id=str(uuid4()), schema_version="0.8.0"),
            geometry=None,
        )
    )
    root = model.record_at("").record
    assert root.has_field("geometry") and root.to_data()["geometry"] is None
    with pytest.raises(MissingReferenceError):
        model.record_at("/geometry")


def test_omitted_record_is_not_synthesized():
    model = Model.from_data(
        dict(metadata=dict(id=str(uuid4()), schema_version="0.8.0"))
    )
    assert not model.record_at("").record.has_field("system")
    with pytest.raises(MissingReferenceError):
        model.record_at("/system")


def test_locations_and_records_are_immutable_but_exports_are_detached(inspected):
    model, _ = inspected
    location = model.record_at("/metadata")
    for field, value in [("record", None), ("owner_id", uuid4()), ("path", "/other")]:
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(location, field, value)
    with pytest.raises(AttributeError):
        location.record.name = "Changed"
    detached = location.record.to_data()
    detached["name"] = "Changed"
    assert model.metadata.name != "Changed"
    assert location.record.name != "Changed"


def test_locations_remain_scoped_to_their_model_revision(inspected):
    before, _ = inspected
    path = "/system/entities/0"
    old = before.record_at(path)
    system = before.system.to_data()
    system["entities"][0]["name"] = "Changed only in the new revision"
    after = before.revise(Update(system=System.from_data(system)))
    new = after.record_by_id(old.record.id)
    assert new.path == old.path and new.owner_id == old.owner_id
    assert new.record.name != old.record.name
    assert before.record_by_id(old.record.id).record == old.record
    assert after.record_at(path).record == new.record
    for model, missing in ((before, after.id), (after, before.id)):
        with pytest.raises(MissingReferenceError):
            model.record_by_id(missing)
    assert before.record_by_id(before.id).path == "/metadata"
    assert after.record_by_id(after.id).path == "/metadata"


def prohibit_whole_document_work(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Exact lookup must not reconstruct, export, index or walk the Model"
        )

    monkeypatch.setattr(index_module, "walk", forbidden)
    monkeypatch.setattr(RecordIndex, "build", forbidden)
    for cls in (Model, Record):
        monkeypatch.setattr(cls, "from_data", forbidden)
        monkeypatch.setattr(cls, "to_data", forbidden)
    monkeypatch.setattr(Record, "_set_data", forbidden)
    original_field = Record._field

    def selected_field(record, name):
        field = _slot_map(record._kind)[name]
        if field["many"] or field["mapping"]:
            raise AssertionError("Exact lookup must not decode sibling collections")
        return original_field(record, name)

    monkeypatch.setattr(Record, "_field", selected_field)
    wrappers = []

    def factory(cls):
        def allocate(_factory):
            wrappers.append(cls.__name__)
            return cls.__new__(cls)

        return SimpleNamespace(__new__=allocate)

    # Leave class construction slots intact: changing Record.__new__ can leave
    # CPython's inherited allocation slot changed even after monkeypatch undo.
    # Each proxy returns the actual generated class; only this registry is replaced.
    monkeypatch.setattr(
        records_module,
        "_TYPES",
        {kind: factory(cls) for kind, cls in records_module._TYPES.items()},
    )
    return wrappers


def test_lookup_guard_restores_generated_constructors(inspected, monkeypatch):
    model, _ = inspected
    original_types = records_module._TYPES
    constructors = (
        Record.__new__,
        Entity.__new__,
        Quantity.__new__,
        ModelRecord.__new__,
    )
    with monkeypatch.context() as guard:
        wrappers = prohibit_whole_document_work(guard)
        assert model.record_at("/system/entities/0").path == "/system/entities/0"
        assert wrappers == ["System", "Entity"]
    assert records_module._TYPES is original_types
    assert (
        Record.__new__,
        Entity.__new__,
        Quantity.__new__,
        ModelRecord.__new__,
    ) == constructors
    entity = Entity(id=uuid4(), name="Constructed after the lookup guard")
    assert Quantity(magnitude=0, units="m^2").magnitude == 0
    after = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.8.0"),
        system=System(entities=(entity,)),
    )
    assert after.entity(entity.id) == entity


def test_lookup_creates_only_selected_chain_wrappers(inspected, monkeypatch):
    model, oracle = inspected
    target = next(
        row for row in reversed(oracle) if type(row[0]).__name__ == "PropertyContent"
    )
    record, owner, path = target
    chain = [
        type(row[0]).__name__
        for row in oracle
        if row[2] and (path == row[2] or path.startswith(row[2] + "/"))
    ]
    wrappers = prohibit_whole_document_work(monkeypatch)
    location = model.record_at(path)
    assert type(location.record) is type(record)
    assert location.record == record
    assert location.owner_id == owner and location.path == path
    assert wrappers == chain
    wrappers.clear()
    identified = next(row for row in oracle if type(row[0]).__name__ == "Value")
    location = model.record_by_id(identified[0].id)
    assert location.record == identified[0]
    assert location.owner_id == identified[1] and location.path == identified[2]
    assert wrappers == []


def test_late_value_and_claim_do_not_require_visiting_twenty_thousand_records(
    monkeypatch,
):
    data = dict(
        metadata=dict(id=str(UUID(int=1)), schema_version="0.8.0"),
        system=dict(
            entities=[
                dict(
                    id=str(UUID(int=2)),
                    characteristics=dict(
                        values=[
                            dict(
                                id=str(UUID(int=3)),
                                key="wide",
                                kind="property",
                                content=dict(
                                    kind="list",
                                    items=[dict(kind="null") for _ in range(20001)],
                                ),
                            ),
                            dict(
                                id=str(UUID(int=4)),
                                key="late",
                                kind="property",
                                content=dict(kind="boolean", text="False"),
                            ),
                        ]
                    ),
                )
            ]
        ),
        provenance=dict(
            claims=[
                dict(
                    id=str(UUID(int=5)),
                    kind="asserted",
                    method=dict(code="inspection-test"),
                    content={"id": str(UUID(int=6)), "untouched": [None, False, 0]},
                )
            ]
        ),
    )
    model = Model.from_data(data)
    oracle = tuple(walk(ModelRecord.from_data(data)))
    selected = [
        (position, record, owner, path)
        for position, (record, owner, path) in enumerate(oracle)
        if type(record).__name__ in ("Value", "Claim")
        and record.id in (UUID(int=4), UUID(int=5))
    ]
    assert len(selected) == 2 and all(position > 20000 for position, *_ in selected)
    wrappers = prohibit_whole_document_work(monkeypatch)
    for _, record, owner, path in selected:
        wrappers.clear()
        location = model.record_at(path)
        assert (
            location.record == record
            and location.owner_id == owner
            and location.path == path
        )
        assert len(wrappers) <= len(path.split("/")) - 1
        wrappers.clear()
        location = model.record_by_id(record.id)
        assert (
            location.record == record
            and location.owner_id == owner
            and location.path == path
        )
        assert wrappers == []
