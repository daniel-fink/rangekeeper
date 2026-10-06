"""Acceptance tests for the schema-derived immutable record boundary."""

from copy import deepcopy
import inspect
import json
from pathlib import Path
import subprocess
import sys
import typing
from uuid import UUID, uuid4

import pytest
import yaml

from rangekeeper._schema import records as r
from rangekeeper._schema.validation import schema_for, validate
from rangekeeper.errors import ValidationError
from rangekeeper.model.validation import validate as validate_model
from rangekeeper.specification.validation import (
    validate_records as validate_specification,
)
from rangekeeper.run.validation import validate_records as validate_run

EXAMPLES = Path(__file__).resolve().parents[2] / "schema/examples"
FIXTURES = sorted(
    path
    for path in EXAMPLES.glob("*.yaml")
    if path.stem.startswith(("model", "specification", "run"))
)


def load(path):
    return yaml.safe_load(path.read_text())


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_fixture_roundtrip_and_typed_nested_access(path):
    kind = path.stem.split("-")[0].capitalize()
    data = load(path)
    record = getattr(r, kind).from_data(data)
    assert record.to_data() == data
    assert record.metadata.id == UUID(data["metadata"]["id"])
    assert getattr(r, kind).from_json(json.dumps(data)) == record
    data["metadata"]["name"] = "mutated input"
    detached = record.to_data()
    detached["metadata"]["name"] = "mutated output"
    assert record.metadata.name not in ("mutated input", "mutated output")


def test_constructor_and_field_types_are_explicit():
    for cls in r._TYPES.values():
        hints = typing.get_type_hints(cls.__init__)
        assert "return" in hints
        for name, field in inspect.signature(cls).parameters.items():
            assert field.kind is inspect.Parameter.KEYWORD_ONLY
            assert name in hints
            assert (
                typing.get_type_hints(getattr(cls, name).fget)["return"]
                is not typing.Any
            )
    assert isinstance(r.Assembly(id=uuid4()), r.Entity)
    with pytest.raises(TypeError):
        r.Entity()
    with pytest.raises(TypeError):
        r.Entity(id=uuid4(), unexpected=True)


def test_presence_zero_false_and_null():
    absent = r.Characteristics()
    empty = r.Characteristics(values=())
    null = r.Characteristics(values=None)
    assert absent.values == empty.values == ()
    assert null.values is None
    assert [v.to_data() for v in (absent, empty, null)] == [
        {},
        {"values": []},
        {"values": None},
    ]
    assert not absent.has_field("values") and null.has_field("values")
    with pytest.raises(KeyError):
        absent.has_field("not_a_field")
    assert r.Quantity(magnitude=0, units="dimensionless").magnitude == 0
    assert r.Expression(id=uuid4(), kind="boolean", boolean=False).boolean is False
    with pytest.raises(ValidationError):
        r.Expression(id=uuid4(), kind="boolean", boolean=None)


@pytest.mark.parametrize(
    "magnitude", [True, "1", float("nan"), float("inf"), float("-inf")]
)
def test_invalid_numeric_inputs(magnitude):
    with pytest.raises((ValidationError, TypeError, ValueError)):
        r.Quantity(magnitude=magnitude, units="dimensionless")


def test_recursive_immutability_and_detached_opaque_content():
    original = {"items": [0, False, None, {"value": "old"}]}
    record = r.Claim(
        id=uuid4(), kind="asserted", method=r.Method(code="manual"), content=original
    )
    original["items"][3]["value"] = "changed"
    assert record.content["items"][3]["value"] == "old"
    with pytest.raises(TypeError):
        record.content["items"][3]["value"] = "changed"
    with pytest.raises(AttributeError):
        record.kind = "sourced"
    with pytest.raises(AttributeError):
        del record._data
    with pytest.raises(AttributeError):
        record._set_data(record.to_data())
    model = r.Model.from_data(load(EXAMPLES / "model.yaml"))
    with pytest.raises(AttributeError):
        model.metadata.name = "changed"
    with pytest.raises(AttributeError):
        model.system.entities.append(None)


def test_uuid_scope_and_union():
    identity = UUID("AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA")
    record = r.Claim(
        id=identity,
        kind="asserted",
        method=r.Method(code="manual"),
        content={"id": str(identity).upper()},
        sources=(r.Location(source=identity), identity),
    )
    assert record.id == identity
    assert record.sources[0].source == record.sources[1] == identity
    assert record.to_data()["id"] == str(identity)
    assert record.content["id"] == str(identity).upper()
    assert (
        r.Claim.from_data({**record.to_data(), "id": str(identity).upper()}).id
        == identity
    )
    with pytest.raises(TypeError):
        r.Claim(
            id=identity,
            kind="asserted",
            method=r.Method(code="manual"),
            content=identity,
        )
    with pytest.raises(TypeError):
        r.Claim(
            id=identity,
            kind="asserted",
            method=r.Method(code="manual"),
            content={},
            sources=(r.Quantity(magnitude=1, units="m"),),
        )


def test_expression_shape_and_order():
    left = r.Expression(
        id=uuid4(),
        kind="quantity",
        quantity=r.Quantity(magnitude=2, units="dimensionless"),
    )
    right = r.Expression(
        id=uuid4(),
        kind="quantity",
        quantity=r.Quantity(magnitude=1, units="dimensionless"),
    )
    expression = r.Expression(
        id=uuid4(), kind="binary", operator="subtract", operands=(left, right)
    )
    assert tuple(node.id for node in expression.operands) == (left.id, right.id)
    assert r.Expression.from_data(expression.to_data()) == expression
    with pytest.raises(ValidationError):
        r.Expression(
            id=uuid4(),
            kind="binary",
            operator="not_an_operator",
            operands=(left, right),
        )
    with pytest.raises(ValidationError):
        r.Expression(id=uuid4(), kind="quantity")


@pytest.mark.parametrize(
    "address",
    [
        {"line": "1"},
        {"line": {"value": "1"}},
        {"line": {"key": "line", "value": "1"}},
        {},
        None,
    ],
)
def test_keyed_inline_dictionary_preserves_wire_forms(address):
    source = uuid4()
    location = r.Location(source=source, address=address)
    assert location.to_data() == {"source": str(source), "address": address}
    assert r.Location.from_data(location.to_data()) == location
    if address:
        with pytest.raises(TypeError):
            location.address["line"] = "2"
    assert r.Location(source=source).address == {}


@pytest.mark.parametrize(
    "value", [object(), {1: "bad key"}, {"bad": float("nan")}, {"bad": UUID(int=0)}]
)
def test_opaque_json_rejects_non_json(value):
    with pytest.raises((TypeError, ValueError)):
        r.Claim(
            id=uuid4(), kind="asserted", method=r.Method(code="manual"), content=value
        )


def test_cycles_duplicate_keys_and_structure_diagnostics():
    cyclic = {}
    cyclic["cycle"] = cyclic
    with pytest.raises(ValueError, match="cyclic"):
        r.Claim(
            id=uuid4(), kind="asserted", method=r.Method(code="manual"), content=cyclic
        )
    with pytest.raises(ValueError, match="duplicate JSON key"):
        r.Model.from_json('{"metadata":{"id":"a","id":"b"}}')
    report = validate("Model", {"metadata": {"id": "bad", "schema_version": "0.5.0"}})
    assert not report.valid
    assert any(issue.path == "/metadata/id" for issue in report.issues)
    with pytest.raises(ValidationError) as raised:
        report.raise_if_invalid()
    assert raised.value.report is report
    schema = schema_for("Quantity")
    schema["$defs"]["Quantity"].clear()
    assert not validate("Quantity", {}).valid


def test_model_semantics_are_separate_from_record_shape():
    data = load(EXAMPLES / "model.yaml")
    assert validate_model(data).valid
    assert validate_model(r.Model.from_data(data)).valid
    data["metadata"]["schema_version"] = "999.0.0"
    record = r.Model.from_data(data)
    report = validate_model(record)
    assert not report.valid and report.issues[0].code == "semantic.contract"
    assert report.issues[0].document_id == record.metadata.id
    assert not validate_model({"metadata": {}}).valid
    assert not validate_model(r.Entity(id=uuid4())).valid


def test_shared_specification_and_run_validation():
    models = {
        data["metadata"]["id"]: data for data in map(load, EXAMPLES.glob("model*.yaml"))
    }
    specs = {
        data["metadata"]["id"]: data
        for data in map(load, EXAMPLES.glob("specification*.yaml"))
    }
    runs = {
        data["metadata"]["id"]: data for data in map(load, EXAMPLES.glob("run*.yaml"))
    }
    specification = load(EXAMPLES / "specification-forward.yaml")
    assert validate_specification(
        specification, models=models, specifications=specs
    ).valid
    assert validate_specification(
        load(EXAMPLES / "specification-batch.yaml"), models=models, specifications=specs
    ).valid
    run = load(EXAMPLES / "run-forward.yaml")
    assert validate_run(run, models=models, specifications=specs, runs=runs).valid
    broken = deepcopy(run)
    broken["outputs"] = [str(uuid4())]
    assert not validate_run(broken, models=models, specifications=specs, runs={}).valid
    broken_models = deepcopy(models)
    next(iter(broken_models.values()))["metadata"]["id"] = "bad"
    assert not validate_specification(
        specification, models=broken_models, specifications=specs
    ).valid


def test_lightweight_imports():
    script = """
import sys
from rangekeeper._schema.records import Model, Metadata
from rangekeeper.model.validation import validate
from uuid import uuid4
assert validate(Model(metadata=Metadata(id=uuid4(), schema_version="0.5.0"))).valid
for prefix in ("linkml", "linkml_runtime", "numpy", "pandas", "matplotlib", "pint", "pyomo", "specklepy", "rangekeeper.graph"):
    assert not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules), prefix
"""
    subprocess.run([sys.executable, "-c", script], check=True)


def test_record_equality_distinguishes_json_booleans_and_numbers():
    identity = uuid4()
    common = dict(id=identity, kind="asserted", method=r.Method(code="manual"))
    assert r.Claim(content={"value": False}, **common) != r.Claim(
        content={"value": 0}, **common
    )
    assert r.Claim(content={"a": 0, "b": False}, **common) == r.Claim(
        content={"b": False, "a": 0}, **common
    )


def test_timestamp_formats_are_enforced():
    implementations = (r.Implementation(kind="evaluator", name="test", version="1"),)
    r.Runtime(implementations=implementations, started_at="2026-10-02T00:00:00Z")
    for timestamp in ("nonsense", "2026-10-02T00:00:00", "2026-02-30T00:00:00Z"):
        with pytest.raises(ValidationError):
            r.Runtime(implementations=implementations, started_at=timestamp)


def test_slot_lookup_cache_is_immutable_and_public_metadata_is_detached():
    from rangekeeper._schema.validation import _slot_map, slots_for

    declaration = _slot_map("Value")
    with pytest.raises(TypeError):
        declaration["id"]["options"][0]["kind"] = "string"
    detached = slots_for("Value")
    detached["id"]["options"][0]["kind"] = "string"
    assert slots_for("Value")["id"]["options"][0]["kind"] != "string"
    assert _slot_map("Value") is declaration
