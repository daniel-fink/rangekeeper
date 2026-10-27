"""Compare frozen Model semantics with the original detached-export boundary."""

import hashlib
import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

import pytest
import yaml

from rangekeeper import Model
from rangekeeper.model import validation
from rangekeeper.quantity import default_units
from rangekeeper.schema.index import RecordIndex
from rangekeeper.schema.records import Entity, Measure
from rangekeeper.schema.records import Model as ModelRecord
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import ValidationError
from rangekeeper.shared.validation import bounded, checked

EXAMPLES = Path(__file__).resolve().parents[1] / "examples/schema"
MISSING = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def original_validate(
    record,
    *,
    index=None,
    initial_issues=None,
    history=(),
    units=default_units,
):
    """Retain the exact original orchestration, including unconditional export.

    Baseline: 8c50e06bd045b1298da15be5be296a1150d2d339, model/validation.py
    SHA256: a1e6de54aaf4a015fbef6c0f7986c665cc2068576c476ba0fb153b768b016541.
    The ignored campaign snapshot is provenance only, never a test dependency.
    Domain helpers are unchanged by this experiment; the candidate _validate is
    deliberately not called here.
    """
    issues = list(initial_issues or ())
    prior = [
        checked("Metadata", value, f"/history/{position}", issues)
        for position, value in enumerate(history)
    ]
    if issues:
        return ValidationReport(tuple(issues))
    assert record is not None
    data = record.to_data()
    report = bounded(
        issues,
        lambda: validation.check_model(
            data, document_version("Model"), prior, index=index
        ),
        document=data,
    )
    if not report.valid:
        return report
    if index is None:
        index = RecordIndex.build(record)
    return ValidationReport(
        validation.recorded_unit_issues(
            record,
            measure=lambda id: index.get(id, Measure),
            units=units,
            document_id=record.metadata.id,
        )
    )


def wire(data):
    """Also distinguish scalar types, signed zero, presence and collection order."""
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def load(name="model"):
    return yaml.safe_load((EXAMPLES / f"{name}.yaml").read_text())


def outcome(operation):
    try:
        result = operation()
    except Exception as error:
        report = getattr(error, "report", None)
        return ("error", type(error), str(error), report.issues if report else None)
    if isinstance(result, ValidationReport):
        return ("report", result.valid, result.issues)
    return ("model", wire(result.to_data()))


def compare_record(data, *, indexed=False, history=(), valid=None, error=None):
    before, prior = wire(data), wire(history)
    record = ModelRecord.from_data(data)
    exported = wire(record.to_data())
    index = RecordIndex.build(record) if indexed else None
    arguments = dict(index=index, history=history)
    expected = outcome(lambda: original_validate(record, **arguments))
    actual = outcome(lambda: validation._validate(record, **arguments))
    assert actual == expected
    assert wire(data) == before
    assert wire(history) == prior
    assert wire(record.to_data()) == exported
    if error is not None:
        assert actual == ("error", *error, None)
        return actual
    assert actual[0] == "report", actual
    if valid is not None:
        assert actual[1] is valid, actual
    return actual[2]


def fault(data, name):
    system = data["system"]
    value = system["entities"][1]["characteristics"]["values"][0]
    formulation = system["formulations"][0]
    if name == "duplicate_identity":
        system["assemblies"][0]["id"] = system["entities"][0]["id"]
    elif name == "missing_reference":
        system["relationships"][0]["target"] = MISSING
    elif name == "wrong_kind_reference":
        system["relationships"][0]["target"] = value["id"]
    elif name == "missing_classification":
        system["entities"][0]["classification"] = MISSING
    elif name == "membership_cycle":
        system["assemblies"][0]["entities"].append(system["assemblies"][0]["id"])
    elif name == "definition_code":
        data["definitions"]["measures"][1]["code"] = "area"
    elif name == "formulation_code":
        system["formulations"][1]["code"] = formulation["code"]
    elif name == "binding_target":
        formulation["bindings"][0]["value"] = MISSING
    elif name == "expression_target":
        expression = formulation["formulations"][0]["expressions"][0]
        expression["operands"][0]["target"]["target"] = MISSING
    elif name == "constraint_predicate":
        formulation["formulations"][0]["constraints"][0]["predicate"] = value["id"]
    elif name == "provenance_cycle":
        claim = next(c for c in data["provenance"]["claims"] if c["kind"] == "derived")
        claim["sources"] = [claim["id"]]
    elif name == "missing_source":
        data["provenance"]["claims"][0]["sources"][0]["source"] = MISSING
    elif name == "duplicate_fact_claim":
        fact = data["provenance"]["facts"][0]
        fact["claims"].append(fact["claims"][0])
    elif name == "self_previous":
        data["metadata"]["previous"] = data["metadata"]["id"]
    elif name == "current_previous":
        data["metadata"]["previous"] = value["id"]
    elif name == "unsupported_version":
        data["metadata"]["schema_version"] = "999"
    elif name == "incompatible_units":
        value["quantity"]["units"] = "second"
    elif name == "unknown_units":
        data["definitions"]["measures"][-1]["units"] = "missing_test_unit"
    elif name == "opaque_content":
        data["provenance"]["claims"][0]["content"] = {
            "id": value["id"],
            "units": "not_a_unit",
            "items": [False, 0, -0.0, None, [], {"id": value["id"]}],
        }
    else:
        raise AssertionError(name)


FAULTS = (
    "missing_reference",
    "wrong_kind_reference",
    "missing_classification",
    "membership_cycle",
    "definition_code",
    "formulation_code",
    "binding_target",
    "expression_target",
    "constraint_predicate",
    "provenance_cycle",
    "missing_source",
    "duplicate_fact_claim",
    "self_previous",
    "current_previous",
    "unsupported_version",
    "incompatible_units",
    "unknown_units",
)


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize(
    "name", ["model", "model-forward-output", "model-inverse-output"]
)
def test_canonical_examples_with_and_without_existing_index(name, indexed):
    compare_record(load(name), indexed=indexed, valid=True)


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize("name", FAULTS + ("opaque_content",))
def test_semantic_reports_preserve_all_ordered_fields(name, indexed):
    data = load()
    fault(data, name)
    compare_record(data, indexed=indexed, valid=name == "opaque_content")


def test_duplicate_declarations_before_index_construction():
    data = load()
    fault(data, "duplicate_identity")
    issues = compare_record(data, valid=False)
    assert issues[0].code == "semantic.identity"
    assert issues[0].path == "/system/assemblies/0/id"


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize(
    "first,second",
    [
        ("unsupported_version", "definition_code"),
        ("definition_code", "formulation_code"),
        ("formulation_code", "missing_reference"),
        ("missing_reference", "missing_source"),
        ("missing_source", "self_previous"),
        ("self_previous", "incompatible_units"),
    ],
)
def test_multiple_faults_keep_the_original_stage_precedence(first, second, indexed):
    earlier, later, combined = load(), load(), load()
    fault(earlier, first)
    fault(later, second)
    fault(combined, first)
    fault(combined, second)
    first_issues = compare_record(earlier, indexed=indexed, valid=False)
    second_issues = compare_record(later, indexed=indexed, valid=False)
    assert first_issues != second_issues
    assert compare_record(combined, indexed=indexed, valid=False) == first_issues


def test_multiple_unit_issues_keep_walker_order():
    data = load()
    fault(data, "unknown_units")
    fault(data, "incompatible_units")
    issues = compare_record(data, indexed=True, valid=False)
    assert [issue.code for issue in issues] == ["semantic.units", "semantic.units"]
    assert [issue.path for issue in issues] == [
        "/definitions/measures/6/units",
        "/system/entities/1/characteristics/values/0/quantity/units",
    ]


@pytest.mark.parametrize("name", ("unchanged", "duplicate_identity") + FAULTS)
def test_public_mapping_and_constructor_outcomes_remain_equal(monkeypatch, name):
    data = load()
    if name != "unchanged":
        fault(data, name)
    before = wire(data)
    actual = (
        outcome(lambda: validation.validate(data)),
        outcome(lambda: Model.from_data(data)),
    )
    with monkeypatch.context() as patch:
        patch.setattr(validation, "_validate", original_validate)
        expected = (
            outcome(lambda: validation.validate(data)),
            outcome(lambda: Model.from_data(data)),
        )
    assert actual == expected
    assert wire(data) == before


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "duplicate",
        "current",
        "current_content",
        "cycle",
        "invalid_structure",
    ],
)
def test_history_context_remains_ordered_and_detached(case, indexed):
    data = load()
    prior = {"id": data["metadata"]["previous"], "schema_version": "0.7.0"}
    history = [prior]
    if case == "duplicate":
        history.append(deepcopy(prior))
    elif case == "current":
        prior["id"] = data["metadata"]["id"]
    elif case == "current_content":
        prior["id"] = data["system"]["entities"][0]["id"]
    elif case == "cycle":
        prior["previous"] = data["metadata"]["id"]
    elif case == "invalid_structure":
        prior["id"] = "invalid"
        history.append({"id": 0, "schema_version": False})
    compare_record(data, indexed=indexed, history=history, valid=case == "valid")


def test_initial_and_history_structural_issues_prevent_export(monkeypatch):
    initial = [Issue("structure.test", "earlier fault", path="/first")]
    history = [{"id": "invalid", "schema_version": False}, {}]
    expected = original_validate(None, initial_issues=initial, history=history)

    def forbidden(*args, **kwargs):
        raise AssertionError("semantic stage entered after structural issues")

    with monkeypatch.context() as patch:
        patch.setattr(validation, "check_model", forbidden)
        patch.setattr(ModelRecord, "to_data", forbidden)
        actual = validation._validate(None, initial_issues=initial, history=history)
    assert actual.issues == expected.issues
    assert actual.issues[0] == initial[0]
    assert any(issue.path.startswith("/history/0/") for issue in actual.issues[1:])
    assert any(issue.path == "/history/1" for issue in actual.issues[1:])
    assert initial == [Issue("structure.test", "earlier fault", path="/first")]


@pytest.mark.parametrize("value", [None, False, [], {}, {"metadata": None}])
def test_raw_invalid_mapping_entrypoints_keep_structural_diagnostics(
    monkeypatch, value
):
    before = wire(value)
    actual = outcome(lambda: validation.validate(value))
    with monkeypatch.context() as patch:
        patch.setattr(validation, "_validate", original_validate)
        expected = outcome(lambda: validation.validate(value))
    assert actual == expected
    assert actual[0:2] == ("report", False)
    assert wire(value) == before


def flow_model():
    data = load()
    values = data["system"]["entities"][0]["characteristics"]["values"]
    values.append(
        {
            "id": str(UUID(int=900)),
            "key": "cash",
            "kind": "flow",
            "measure": data["definitions"]["measures"][0]["id"],
            "flow": {
                "units": "m^2",
                "movements": [
                    {
                        "id": str(UUID(int=901)),
                        "key": "zero",
                        "date": "2026-01-01",
                        "magnitude": -0.0,
                    },
                    {
                        "id": str(UUID(int=902)),
                        "key": "unknown",
                        "date": "2026-01-02",
                        "magnitude": None,
                    },
                    {
                        "id": str(UUID(int=903)),
                        "key": "absent",
                        "date": "2026-01-03",
                    },
                ],
            },
        }
    )
    return data


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize("case", ["valid", "coordinate", "claims", "units"])
def test_flow_presence_and_semantics_match_detached_export(case, indexed):
    data = flow_model()
    flow = data["system"]["entities"][0]["characteristics"]["values"][-1]["flow"]
    if case == "coordinate":
        flow["movements"][0].pop("date")
    elif case == "claims":
        flow["movements"][0]["claims"] = [MISSING]
    elif case == "units":
        flow["units"] = "second"
    compare_record(data, indexed=indexed, valid=case == "valid")


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize("case", ["valid", "invalid_content"])
def test_recursive_property_content_is_still_checked(case, indexed):
    data = load()
    content = {
        "kind": "list",
        "items": [
            {"kind": "integer", "text": "0"},
            {
                "kind": "mapping",
                "entries": [
                    {
                        "key": {"kind": "string", "text": "x"},
                        "value": {"kind": "integer", "text": "1"},
                    }
                ],
            },
        ],
    }
    if case == "invalid_content":
        content["items"][0]["text"] = "not-an-integer"
    data["system"]["entities"][0]["characteristics"]["values"].append(
        {
            "id": str(UUID(int=904)),
            "key": "property",
            "kind": "property",
            "content": content,
        }
    )
    compare_record(data, indexed=indexed, valid=case == "valid")


@pytest.fixture(scope="module")
def scenario_data():
    from rangekeeper.duration import Frequency, make_periods
    from rangekeeper.model.scenario import market

    # Build accepted data through the old boundary so candidate failure cannot
    # prevent the comparison fixture from being constructed.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(validation, "_validate", original_validate)
        base = Model.from_data(
            {"metadata": {"id": str(UUID(int=910)), "schema_version": "0.7.0"}}
        )
        plan = market.make_plan(
            id=UUID(int=911),
            periods=make_periods(date(2026, 1, 1), frequency=Frequency.YEAR, count=2),
            seed=123,
        )
        return market.generate(base, plan, scenario_keys=["equivalence"])[
            0
        ].model.to_data()


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize("case", ["valid", "parameter", "binding", "availability"])
def test_captured_scenario_contracts_match_export(scenario_data, case, indexed):
    data = deepcopy(scenario_data)
    realization = data["provenance"]["scenarios"][0]
    if case == "parameter":
        parameter = next(
            p for p in realization["plan"]["parameters"] if p["name"] == "cap_rate"
        )
        parameter["quantity"]["magnitude"] = 0
    elif case == "binding":
        realization["outputs"][0]["value"] = MISSING
    elif case == "availability":
        realization["availability"].append(deepcopy(realization["availability"][0]))
    compare_record(
        data,
        indexed=indexed,
        valid=case == "valid",
        error=(
            (ValueError, "scenario parameter below its bound: cap_rate")
            if case == "parameter"
            else None
        ),
    )


@pytest.mark.parametrize("section", ["definitions", "system", "provenance"])
@pytest.mark.parametrize("presence", ["absent", "null", "empty"])
def test_optional_section_presence_is_not_collapsed(monkeypatch, section, presence):
    data = {"metadata": {"id": str(UUID(int=920)), "schema_version": "0.7.0"}}
    if presence != "absent":
        data[section] = None if presence == "null" else {}
    if presence == "null":
        before = wire(data)
        actual = (
            outcome(lambda: validation.validate(data)),
            outcome(lambda: Model.from_data(data)),
        )
        with monkeypatch.context() as patch:
            patch.setattr(validation, "_validate", original_validate)
            expected = (
                outcome(lambda: validation.validate(data)),
                outcome(lambda: Model.from_data(data)),
            )
        assert actual == expected
        assert actual[0][0:2] == ("report", False)
        assert actual[1][0:2] == ("error", ValidationError)
        assert wire(data) == before
        return
    compare_record(data, valid=True)
    assert wire(Model.from_data(data).to_data()) == wire(data)


def geometry_model():
    data = load()
    data["metadata"]["schema_version"] = document_version("Model")
    files = [{"path": "native/model.json", "sha256": "a" * 64, "size": 2}]
    digest = hashlib.sha256(
        json.dumps(
            files,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    data["geometry"] = {
        "pin": {
            "provider": "test",
            "format": "json",
            "format_version": "1",
            "specification": "test/v1",
            "specification_digest": "b" * 64,
            "content_digest": digest,
            "files": files,
        },
        "mappings": [
            {
                "entity": data["system"]["entities"][0]["id"],
                "element": {
                    "namespace": "test",
                    "kind": "object",
                    "key": "0",
                    "placement": ["a", "b"],
                },
            }
        ],
    }
    return data


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize(
    "case", ["valid", "null", "digest", "mapping", "duplicate", "legacy"]
)
def test_geometry_fallback_keeps_existing_semantics(case, indexed):
    data = geometry_model()
    if case == "null":
        data["geometry"] = None
    elif case == "digest":
        data["geometry"]["pin"]["content_digest"] = "c" * 64
    elif case == "mapping":
        data["geometry"]["mappings"][0]["entity"] = MISSING
    elif case == "duplicate":
        data["geometry"]["mappings"] *= 2
    elif case == "legacy":
        data["metadata"]["schema_version"] = "0.7.0"
    compare_record(data, indexed=indexed, valid=case in {"valid", "null"})


@pytest.mark.parametrize("case", ["exact", "geometry", "null", "subclass"])
def test_only_exact_geometry_absent_records_borrow_frozen_data(monkeypatch, case):
    class DerivedModel(ModelRecord):
        pass

    data = geometry_model() if case in {"geometry", "null"} else load()
    if case == "null":
        data["geometry"] = None
    kind = DerivedModel if case == "subclass" else ModelRecord
    record = kind.from_data(data)
    before = wire(record.to_data())
    exported, observed = [], []
    original_export, original_check = ModelRecord.to_data, validation.check_model

    def export(self):
        if self is record:
            exported.append(self)
        return original_export(self)

    def check(actual, *args, **kwargs):
        observed.append(actual)
        return original_check(actual, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(ModelRecord, "to_data", export)
        patch.setattr(validation, "check_model", check)
        assert validation._validate(record).valid
    assert len(observed) == 1
    if case == "exact":
        assert not exported
        assert observed[0] is record._data
        assert isinstance(observed[0], MappingProxyType)
        assert isinstance(observed[0]["system"]["entities"], tuple)
    else:
        assert exported == [record]
        assert type(observed[0]) is dict
        assert type(observed[0]["system"]["entities"]) is list
    assert wire(record.to_data()) == before
    # Ordinary method spies must not affect later generated constructors.
    assert Entity(id=UUID(int=930)).id == UUID(int=930)


def test_subclass_export_override_is_respected():
    class DerivedModel(ModelRecord):
        def to_data(self):
            result = super().to_data()
            result["metadata"]["previous"] = result["metadata"]["id"]
            return result

    record = DerivedModel.from_data(load())
    expected = original_validate(record)
    actual = validation._validate(record)
    assert actual.issues == expected.issues
    assert not actual.valid
    assert actual.issues[0].message == "self predecessor"


def test_public_facade_and_exports_stay_detached_after_borrowing(monkeypatch):
    data = flow_model()
    fault(data, "opaque_content")
    original = wire(data)
    model = Model.from_data(data)
    expected = original_validate(model._record, index=model._index)
    assert validation.validate(model).issues == expected.issues == ()
    with monkeypatch.context() as patch:
        patch.setattr(validation, "_validate", original_validate)
        assert validation.validate(model).issues == expected.issues
    exported = model.to_data()
    exported["system"]["entities"].clear()
    exported["provenance"]["claims"][0]["content"]["items"].clear()
    data["metadata"]["id"] = MISSING
    data["system"].clear()
    assert wire(model.to_data()) == original
    with pytest.raises(TypeError):
        model._record._data["metadata"]["name"] = "changed"
    assert validation.validate(model).valid
    assert wire(model.to_data()) == original
