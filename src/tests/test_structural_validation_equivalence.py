"""Compare prepared reference dispatch with the unchanged jsonschema oracle."""

import json
from copy import deepcopy
from functools import cache
from pathlib import Path
from uuid import UUID

import pytest
import yaml
from jsonschema import Draft201909Validator, Draft202012Validator, FormatChecker

from rangekeeper import Model
from rangekeeper.io import json as codec
from rangekeeper.schema import records, validation
from rangekeeper.shared.diagnostics import Issue
from rangekeeper.shared.errors import DecodeError

EXAMPLES = Path(__file__).resolve().parents[2] / "examples/schema"
FIXTURES = sorted(
    path
    for path in EXAMPLES.glob("*.yaml")
    if path.stem.startswith(("model", "specification", "run"))
)
KINDS = sorted(validation.schema_for("Model")["$defs"])
IDENTITY = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


@cache
def oracle(kind):
    # This uses the original entry point, without RK's prepared validator class.
    return Draft202012Validator(
        validation.schema_for(kind),
        format_checker=FormatChecker(formats=["date", "date-time"]),
    )


def error_tree(error):
    """Keep diagnostic order, nested alternatives and both path representations."""
    return (
        error.validator,
        error.validator_value,
        error.message,
        list(error.path),
        list(error.absolute_path),
        list(error.schema_path),
        list(error.absolute_schema_path),
        error.schema,
        error.instance,
        [(type(error.cause), str(error.cause))] if error.cause else [],
        [error_tree(child) for child in error.context],
    )


def assert_equivalent(kind, data):
    before = json.dumps(data, ensure_ascii=False, allow_nan=False)
    expected = list(oracle(kind).iter_errors(data))
    actual = list(validation._validator(kind).iter_errors(data))
    assert [error_tree(error) for error in actual] == [
        error_tree(error) for error in expected
    ]
    assert validation.validate(kind, data).issues == tuple(
        Issue(
            f"structure.{error.validator}",
            error.message,
            path="".join(
                "/" + str(part).replace("~", "~0").replace("/", "~1")
                for part in error.absolute_path
            ),
        )
        for error in expected
    )
    assert json.dumps(data, ensure_ascii=False, allow_nan=False) == before
    return not expected


@pytest.mark.parametrize("kind", KINDS)
def test_every_packaged_definition_has_the_same_ordered_diagnostics(kind):
    for value in (None, False, 0, 0.0, -0.0, "", [], {}, {"unexpected": True}):
        assert_equivalent(kind, value)
    definition = validation.schema_for(kind)["$defs"][kind]
    for value in definition.get("enum", ()):
        assert assert_equivalent(kind, value)
    # Exercise every declared property, including optional fields on records
    # which are absent from the positive document examples.
    for name in definition.get("properties", {}):
        for value in (None, False, 0, "", [], {}):
            assert_equivalent(kind, {name: value})


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_canonical_examples_and_nested_failures_match_stock_validation(path):
    kind = path.stem.split("-")[0].capitalize()
    data = yaml.safe_load(path.read_text())
    assert assert_equivalent(kind, data)
    record = getattr(records, kind).from_data(data)
    assert record.to_data() == data
    # Multiple faults establish encounter order across duplicate conjunctions
    # and the reference boundary, not only whether one error is detected.
    data["metadata"]["id"] = "not-a-uuid"
    data["metadata"]["name"] = " "
    data["metadata"]["unknown/~"] = True
    assert not assert_equivalent(kind, data)


@pytest.mark.parametrize(
    "kind,data,valid",
    [
        ("Quantity", {"magnitude": 0, "units": "m"}, True),
        ("Quantity", {"magnitude": -0.0, "units": "m"}, True),
        ("Quantity", {"magnitude": True, "units": "m"}, False),
        ("Characteristics", {}, True),
        ("Characteristics", {"values": None}, True),
        ("Characteristics", {"values": []}, True),
        ("Value", {"id": IDENTITY, "key": "x", "kind": "measurement"}, False),
        ("Expression", {"id": IDENTITY, "kind": "boolean", "boolean": False}, True),
        ("Expression", {"id": IDENTITY, "kind": "boolean", "boolean": None}, False),
        ("Expression", {"id": IDENTITY, "kind": "quantity", "boolean": False}, False),
        ("PropertyContent", {"kind": "integer", "text": "0", "fold": 1.0}, True),
        ("PropertyContent", {"kind": "integer", "text": "0", "fold": True}, False),
        ("PropertyContent", {"kind": "integer", "text": "0", "fold": 2}, False),
        ("Fact", {"target": IDENTITY, "claims": []}, False),
        ("Fact", {"target": [], "claims": [IDENTITY]}, False),
        ("Location", {"source": IDENTITY, "address": {"a/~": {"value": 1}}}, False),
    ],
)
def test_scalar_presence_conditional_bounds_and_pointer_cases(kind, data, valid):
    assert assert_equivalent(kind, data) is valid


@pytest.mark.parametrize(
    "value,valid",
    [
        (None, True),
        ("2024-02-29", True),
        ("2024-02-29T12:30:01Z", True),
        ("2024-02-29T12:30:01+11:00", True),
        ("2023-02-29", False),
        ("2024-02-29T12:30:01", False),
        ("2024-13-01", False),
        (0, False),
    ],
)
def test_date_and_datetime_checks_remain_enabled(value, valid):
    data = {"id": IDENTITY, "name": "source", "checksum": "x", "issued_at": value}
    assert assert_equivalent("Source", data) is valid


def test_recursive_records_keep_order_and_do_not_cache_instance_acceptance():
    leaf = {"kind": "integer", "text": "0"}
    data = {
        "kind": "list",
        "items": [
            leaf,
            {"kind": "mapping", "entries": [{"key": leaf, "value": leaf}]},
        ],
    }
    assert assert_equivalent("PropertyContent", data)
    data["items"][1]["entries"][0]["value"] = {"kind": "bad", "fold": 2}
    assert not assert_equivalent("PropertyContent", data)
    data["items"][1]["entries"][0]["value"] = leaf
    assert assert_equivalent("PropertyContent", data)
    detached = validation.schema_for("PropertyContent")
    detached["$defs"]["PropertyContent"].clear()
    assert not assert_equivalent("PropertyContent", {"kind": "bad"})


def test_public_record_normalization_presence_opaque_content_and_signed_zero():
    source = {
        "id": IDENTITY.upper(),
        "kind": "asserted",
        "method": {"code": "manual"},
        "content": {"id": IDENTITY.upper(), "items": [False, -0.0, None]},
    }
    before = deepcopy(source)
    record = records.Claim.from_data(source)
    assert source == before
    assert record.id == UUID(IDENTITY)
    assert record.to_data() == {**before, "id": IDENTITY}
    assert json.dumps(record.to_data()["content"]) == json.dumps(before["content"])
    exported = record.to_data()
    exported["content"]["items"].clear()
    source["content"].clear()
    assert record.to_data() == {**before, "id": IDENTITY}
    assert [
        records.Characteristics.from_data(data).to_data()
        for data in ({}, {"values": None}, {"values": []})
    ] == [{}, {"values": None}, {"values": []}]


def test_non_json_inputs_and_duplicate_keys_still_fail_at_public_boundaries():
    cyclic = {}
    cyclic["self"] = cyclic
    for value in (cyclic, float("nan"), float("inf"), float("-inf"), {1: "x"}):
        report = validation.validate("Content", value)
        assert not report.valid
        assert report.issues[0].code == "structure.json"
    with pytest.raises(DecodeError, match="duplicate JSON key"):
        codec.loads('{"metadata":{"id":"a","id":"b"}}', kind=Model)


def outcome(data):
    try:
        model = Model.from_data(data)
    except (ValueError, TypeError, LookupError) as error:
        report = getattr(error, "report", None)
        return type(error), str(error), report.issues if report else None
    return "accepted", model.to_data()


@pytest.mark.parametrize(
    "scenario",
    [
        "unchanged",
        "duplicate_identity",
        "missing_reference",
        "wrong_kind_reference",
        "membership_cycle",
        "provenance_cycle",
        "unsupported_version",
        "incompatible_units",
        "invalid_expression",
        "missing_source",
        "duplicate_fact_claim",
        "opaque_identity",
    ],
)
def test_model_semantics_identity_and_provenance_match_original_boundary(
    monkeypatch, scenario
):
    data = yaml.safe_load((EXAMPLES / "model.yaml").read_text())
    system = data["system"]
    value = system["entities"][1]["characteristics"]["values"][0]
    if scenario == "duplicate_identity":
        system["assemblies"][0]["id"] = system["entities"][0]["id"]
    elif scenario == "missing_reference":
        system["relationships"][0]["target"] = IDENTITY
    elif scenario == "wrong_kind_reference":
        system["relationships"][0]["target"] = value["id"]
    elif scenario == "membership_cycle":
        system["assemblies"][0]["entities"].append(system["assemblies"][0]["id"])
    elif scenario == "provenance_cycle":
        claim = next(
            claim
            for claim in data["provenance"]["claims"]
            if claim["kind"] == "derived"
        )
        claim["sources"] = [claim["id"]]
    elif scenario == "unsupported_version":
        data["metadata"]["schema_version"] = "999"
    elif scenario == "incompatible_units":
        value["quantity"]["units"] = "second"
    elif scenario == "invalid_expression":
        expression = system["formulations"][0]["formulations"][0]["expressions"][0]
        expression["operator"] = "not_an_operator"
    elif scenario == "missing_source":
        data["provenance"]["claims"][0]["sources"] = [{"source": IDENTITY}]
    elif scenario == "duplicate_fact_claim":
        fact = data["provenance"]["facts"][0]
        fact["claims"].append(fact["claims"][0])
    elif scenario == "opaque_identity":
        data["provenance"]["claims"][0]["content"] = {
            "id": value["id"],
            "kind": "not_a_record",
            "content": {"id": value["id"]},
        }
    before = deepcopy(data)
    actual = outcome(data)
    with monkeypatch.context() as patch:
        patch.setattr(validation, "_validator", oracle)
        expected = outcome(data)
    assert actual == expected
    if scenario == "provenance_cycle":
        assert actual[2] == (
            Issue(
                "semantic.cycle",
                "Claim dependency cycle",
                UUID(data["metadata"]["id"]),
                "/provenance/claims",
            ),
        )
    assert (actual[0] == "accepted") is (scenario in {"unchanged", "opaque_identity"})
    assert data == before


def test_preparation_is_finite_for_recursive_references_and_reuses_only_schema():
    schema = {
        "$defs": {
            "Tree": {
                "type": "object",
                "properties": {
                    "children": {"type": "array", "items": {"$ref": "#/$defs/Tree"}}
                },
                "additionalProperties": False,
            }
        }
    }
    prepared = validation._prepare_local_validators(schema)
    assert prepared is not None
    target = prepared["Tree"]
    original = Draft202012Validator({**schema, "$ref": "#/$defs/Tree"})
    for data in ({"children": [{"children": [{}]}]}, {"children": [{"bad": 1}]}):
        assert [error_tree(error) for error in target.iter_errors(data)] == [
            error_tree(error) for error in original.iter_errors(data)
        ]
    with pytest.raises(TypeError):
        prepared["Tree"] = None
    # Preparation owns a private copy, not the caller's mutable schema.
    schema["$defs"]["Tree"].clear()
    assert not target.is_valid({"bad": 1})


@pytest.mark.parametrize(
    "definition",
    [
        {"$id": "https://example.invalid/other", "type": "string"},
        {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "string"},
        {"$anchor": "here", "type": "string"},
        {"$dynamicAnchor": "here", "$dynamicRef": "#here"},
        {"$ref": "#/$defs/A/properties/x"},
        {"$ref": "https://example.invalid/other"},
        {"$ref": "#missing"},
        {"$ref": "#/$defs/Missing"},
        False,
    ],
)
def test_unprepared_schema_forms_use_the_stock_path(monkeypatch, definition):
    schema = {"$defs": {"A": definition}}
    assert validation._prepare_local_validators(schema) is None
    # Check the actual entry point selects stock validation. No unresolved
    # reference is executed, and these tests never require network access.
    with monkeypatch.context() as patch:
        patch.setattr(validation, "_artifacts", lambda: (schema, {}, {}))
        oracle.cache_clear()
        validation._validator.cache_clear()
        validation._prepared_validators.cache_clear()
        try:
            assert type(validation._validator("A")) is Draft202012Validator
        finally:
            oracle.cache_clear()
            validation._validator.cache_clear()
            validation._prepared_validators.cache_clear()


@pytest.mark.parametrize(
    "schema,accepted,rejected",
    [
        (
            {"$defs": {"A": {"type": "integer"}}, "allOf": [{"minimum": 2}]},
            2,
            1,
        ),
        (
            {
                "$defs": {
                    "A": {"$ref": "#/$defs/Holder/properties/x"},
                    "Holder": {"properties": {"x": {"type": "integer", "minimum": 2}}},
                }
            },
            2,
            1,
        ),
        (
            {
                "$defs": {
                    "A": {"$ref": "#/$defs/A~1B"},
                    "A/B": {"type": "integer", "minimum": 2},
                }
            },
            2,
            1,
        ),
        (
            {
                "$id": "https://example.invalid/root",
                "$defs": {
                    "A": {
                        "$id": "nested",
                        "$defs": {"B": {"type": "integer", "minimum": 2}},
                        "type": "object",
                        "properties": {"x": {"$ref": "#/$defs/B"}},
                        "required": ["x"],
                    },
                    "B": {"type": "string"},
                },
            },
            {"x": 2},
            {"x": "wrong scope"},
        ),
    ],
)
def test_fallback_preserves_root_assertions_pointer_forms_and_scopes(
    monkeypatch, schema, accepted, rejected
):
    assert validation._prepare_local_validators(schema) is None
    with monkeypatch.context() as patch:
        patch.setattr(validation, "_artifacts", lambda: (schema, {}, {}))
        oracle.cache_clear()
        validation._validator.cache_clear()
        validation._prepared_validators.cache_clear()
        try:
            assert type(validation._validator("A")) is Draft202012Validator
            assert assert_equivalent("A", accepted)
            assert not assert_equivalent("A", rejected)
        finally:
            oracle.cache_clear()
            validation._validator.cache_clear()
            validation._prepared_validators.cache_clear()


def test_preparation_keeps_explicit_2020_draft_despite_packaged_2019_declaration(
    monkeypatch,
):
    schema = {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "$defs": {"A": {"type": "array", "prefixItems": [{"type": "integer"}]}},
    }
    # prefixItems distinguishes the explicitly selected 2020 validator from
    # the dialect declared at the packaged root; 2019 ignores that keyword.
    assert Draft201909Validator({**schema, "$ref": "#/$defs/A"}).is_valid(["bad"])
    with monkeypatch.context() as patch:
        patch.setattr(validation, "_artifacts", lambda: (schema, {}, {}))
        oracle.cache_clear()
        validation._validator.cache_clear()
        validation._prepared_validators.cache_clear()
        try:
            prepared = validation._prepared_validators()
            assert prepared is not None
            assert validation._validator("A") is prepared["A"]
            assert assert_equivalent("A", [1])
            assert not assert_equivalent("A", ["bad"])
        finally:
            oracle.cache_clear()
            validation._validator.cache_clear()
            validation._prepared_validators.cache_clear()
