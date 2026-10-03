"""Format-independent orchestration and explanatory failure regressions."""

from dataclasses import replace

import pytest

from rangekeeper.evidence import Claim, Location, Source
from rangekeeper.workflow import load, run
from rangekeeper.workflow.checking import evaluate
from rangekeeper.workflow.references import references

from .test_workflow import example


@pytest.fixture
def built(tmp_path):
    root, _ = example(tmp_path)
    spec = load(root / "spec")
    result = run(spec, input_root=root / "inputs")
    assert result.output is not None
    return root, spec, result.output


def comparison(left, right):
    return {
        "comparisons": [
            {
                "id": "total",
                "group": "Totals",
                "scope": "all",
                "left": left,
                "right": right,
            }
        ]
    }


def test_operand_missingness_retains_both_sides(built):
    _, _, result = built
    total = {"kind": "table_total", "table": "items", "column": "number_size"}
    checks = evaluate(comparison(total, total), result.model, {}, result.evidence)
    check = checks[0]
    assert check.status == "unavailable"
    assert check.left_missing == check.right_missing and len(check.right_missing) == 1
    assert check.left_known_subtotal == check.right_known_subtotal == 12
    reverse = evaluate(
        comparison({"kind": "value", "value": 12}, total),
        result.model,
        {},
        result.evidence,
    )[0]
    assert reverse.right_missing == check.right_missing
    assert reverse.right_known_subtotal == 12


@pytest.mark.parametrize("missing", ["filter", "value", "support", "scope"])
def test_missing_check_columns_return_outcome(built, missing):
    root, spec, _ = built
    operand = {"kind": "table_total", "table": "items", "column": "number_size"}
    checks = comparison(operand, {"kind": "value", "value": 12})
    if missing == "filter":
        operand["where"] = {"column": "absent", "equals": 1}
    elif missing == "support":
        operand["evidence_columns"] = ["absent"]
    elif missing == "value":
        operand["column"] = "absent"
    else:
        checks["comparisons"][0].update(each="items", scope_column="absent")
    outcome = run(replace(spec, checks=checks), input_root=root / "inputs")
    assert outcome.output is None
    assert outcome.diagnostics[0].code == "missing_column"


def test_record_locations_are_not_lost():
    claim = Claim.sourced(
        1,
        at=Location(
            source=Source(name="Inventory", checksum="a" * 64),
            reference={"record": "42"},
        ),
    )
    rendered = references((claim,))
    assert len(rendered) == 1 and "42" in rendered[0] and "Inventory" in rendered[0]


def test_non_excel_capability_runs_without_runner_changes(tmp_path, monkeypatch):
    from dataclasses import dataclass
    from uuid import uuid5

    from rangekeeper import _structured
    from rangekeeper.io.json import dumps
    from rangekeeper.operation import _Failure, _invoke
    from rangekeeper.evidence import Method
    from rangekeeper.workflow import _audit, catalog, schema
    from rangekeeper.workflow._contracts import (
        OperationDeclaration,
        Produced,
        SourceCheckDeclaration,
    )
    from rangekeeper.workflow.ingestion import fingerprint, tabular
    from rangekeeper.workflow.source_checks import SourceCheck
    from rangekeeper.workflow.specification import StepSpec, WorkflowSpec

    @dataclass(frozen=True)
    class ReadRecords:
        fail: bool = False

        def __post_init__(self):
            if type(self.fail) is not bool:
                raise TypeError("fail requires boolean")

    @dataclass(frozen=True)
    class ExtractRecords:
        input: str

    @dataclass(frozen=True)
    class Records:
        source: Source
        items: tuple[tuple[str, str], ...]

    visits = []

    def read_records(request, inputs, context):
        assert not inputs

        def execute(operation):
            visits.append("read")
            if request.fail:
                raise _Failure("record_source_unavailable", "Source unavailable")
            return Records(
                Source(
                    id=uuid5(context.namespace, "records"),
                    name="Inventory",
                    checksum="a" * 64,
                ),
                (("r1", "P1"),),
            )

        return _invoke(
            Method(code="test.records", version="1"),
            {"fail": request.fail},
            {},
            execute,
        )

    def extract_records(request, inputs, context):
        assert set(inputs) == {request.input}
        with pytest.raises(TypeError):
            inputs["other"] = None
        native = inputs[request.input]
        assert isinstance(native, Records)

        def execute(operation):
            visits.append("extract")
            ids, claims = [], {}
            for address, code in native.items:
                uid = uuid5(native.source.id, address)
                ids.append(uid)
                claims[("rows", str(uid), "code")] = Claim.sourced(
                    code,
                    at=Location(source=native.source, reference={"record": address}),
                    id=uuid5(uid, "code"),
                )
            return tabular.from_claims(
                name=context.name, columns=("code",), row_ids=ids, claims=claims
            )

        return _invoke(
            Method(code="test.extract", version="1"),
            {},
            {"records": _structured.fingerprint(native.items)},
            execute,
        )

    monkeypatch.setitem(
        catalog.OPERATIONS,
        "test.read",
        OperationDeclaration(
            ReadRecords,
            read_records,
            lambda value: Produced(
                value, _structured.fingerprint(value.items), value.source
            ),
            lambda: {"fail": {"type": "boolean"}},
            output="record_document",
        ),
    )
    monkeypatch.setitem(
        catalog.OPERATIONS,
        "test.extract",
        OperationDeclaration(
            ExtractRecords,
            extract_records,
            lambda value: Produced(value, fingerprint(value)),
            lambda: {"input": {"type": "string"}},
            inputs=(("input", "record_document"),),
        ),
    )
    monkeypatch.setitem(
        catalog.SOURCE_CHECKS,
        "test.health",
        SourceCheckDeclaration(
            (("source", "record_document"),),
            lambda s, inputs: (
                SourceCheck(
                    s["id"],
                    "Record health",
                    "passed",
                    len(inputs[s["source"]].items),
                    "Inspected records",
                ),
            ),
        ),
    )
    # Metadata must not query unused optional packages such as openpyxl.
    requested = []
    real_version = _audit.version

    def version(name):
        requested.append(name)
        assert name != "openpyxl"
        return real_version(name)

    monkeypatch.setattr(_audit, "version", version)
    steps = tuple(
        StepSpec.from_mapping(s)
        for s in [
            {"id": "native", "operation": "test.read"},
            {"id": "unrelated", "operation": "test.read"},
            {"id": "records", "operation": "test.extract", "input": "native"},
        ]
    )
    model = {
        "taxonomy": {"code": "inventory", "name": "Inventory"},
        "classifications": [{"code": "machine", "name": "Machine"}],
        "measures": [],
        "objects": [],
        "templates": [
            {
                "id": "items",
                "table": "records",
                "kind": "entity",
                "classification": "machine",
                "name": "Machine {key}",
                "identity_kind": "machine",
                "key": {"column": "code"},
            }
        ],
        "relationships": [],
        "memberships": [],
        "deferred": [{"table": "records", "column": "code", "kind": "record-detail"}],
    }
    checks = {
        "comparisons": [],
        "invariants": ["fact_coverage"],
        "source_checks": [
            {"id": "health", "operation": "test.health", "source": "native"}
        ],
    }
    spec = WorkflowSpec(
        namespace="urn:inventory",
        steps=steps,
        model=model,
        decisions={"decisions": []},
        checks=checks,
        hashes={},
    )
    result = run(spec, input_root=tmp_path).output
    assert result is not None
    assert (
        len(result.model.system.entities) == 1
        and result.model.system.entities[0].code == "P1"
    )
    assert result.source_checks[0].status == "passed"
    assert result.metadata["sources"]["native"]["name"] == "Inventory"
    assert ":row:" in result.metadata["deferred_records"][0]
    assert result.metadata["deferred_evidence"][0]["reference"] == {"record": "r1"}
    assert "native" not in result.evidence
    assert len(result.operations) == 9
    assert schema()["operations"]["test.extract"]["required"] == [
        "id",
        "operation",
        "input",
    ]
    assert "openpyxl" not in result.metadata["dependencies"]
    repeat = run(spec, input_root=tmp_path).output
    assert dumps(result.model) == dumps(repeat.model)
    assert result.metadata == repeat.metadata
    before = len(visits)
    failed = replace(
        spec, steps=(replace(steps[0], request=ReadRecords(True)), *steps[1:])
    )
    outcome = run(failed, input_root=tmp_path)
    assert (
        outcome.output is None
        and outcome.diagnostics[0].code == "record_source_unavailable"
    )
    assert visits[before:] == ["read"]
    wrong = replace(steps[-1], request=ExtractRecords("records"))
    with pytest.raises(ValueError, match="missing or later"):
        replace(spec, steps=(*steps[:-1], wrong))


def test_foundations_do_not_load_workflow_or_adapters():
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from rangekeeper import operation, _structured; assert not any(n.startswith(('rangekeeper.workflow', 'rangekeeper.adapters')) for n in sys.modules)",
        ],
        check=True,
    )


def test_adapter_registration_does_not_load_runner():
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from rangekeeper.adapters.excel import workflow; assert 'rangekeeper.workflow.runtime' not in sys.modules; assert 'rangekeeper.workflow.catalog' not in sys.modules",
        ],
        check=True,
    )


def test_native_code_fingerprints_are_declared(tmp_path):
    from rangekeeper.workflow.implementation import manifests

    adapter = tmp_path / "adapters/records"
    adapter.mkdir(parents=True)
    module = adapter / "reader.py"
    module.write_text("value = 1")
    unused = manifests(tmp_path)[2]
    used = manifests(tmp_path, modules=("adapters/records/",))[2]
    module.write_text("value = 2")
    assert manifests(tmp_path)[2] == unused
    assert manifests(tmp_path, modules=("adapters/records/",))[2] != used


def test_catalog_schema_and_parsing_agree(tmp_path):
    from rangekeeper.workflow import catalog, schema
    from rangekeeper.workflow.specification import StepSpec

    _, docs = example(tmp_path)
    schemas = schema()["operations"]
    for step in docs["sources"]["steps"]:
        definition = schemas[step["operation"]]
        assert not set(step) - set(definition["properties"])
        assert set(definition["required"]) <= set(step)
        parsed = StepSpec.from_mapping(step)
        assert (
            type(parsed.request) is catalog.OPERATIONS[step["operation"]].request_type
        )
        with pytest.raises(ValueError, match="Unknown fields"):
            StepSpec.from_mapping({**step, "unrecognized": True})
        for required in set(definition["required"]) - {"id", "operation"}:
            with pytest.raises((ValueError, TypeError)):
                StepSpec.from_mapping({k: v for k, v in step.items() if k != required})


def test_generic_numeric_source_check(built):
    from uuid import uuid4

    from rangekeeper.workflow.ingestion import Issue, IssueSeverity, tabular
    from rangekeeper.workflow.source_checks import evaluate

    uid = uuid4()
    claim = Claim.sourced(
        None,
        at=Location(
            source=Source(name="Records", checksum="b" * 64), reference={"record": "42"}
        ),
    )
    evidence = tabular.from_claims(
        name="records",
        columns=("value",),
        row_ids=(uid,),
        claims={("rows", str(uid), "value"): claim},
        issues=(
            Issue(
                rule_id="source",
                code="blank_value",
                severity=IssueSeverity.INFO,
                message="Not supplied",
                at=(("rows", str(uid), "value"),),
            ),
        ),
    )
    results = evaluate(
        [
            {
                "id": "missing",
                "operation": "numeric_issues",
                "tables": [{"table": "records", "columns": ["value"]}],
            }
        ],
        {"records": evidence},
    )
    assert len(results) == 1 and results[0].count == 1
    assert "42" in results[0].references[0]
