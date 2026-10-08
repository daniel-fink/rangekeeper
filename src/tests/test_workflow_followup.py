"""Workflow ownership, exact Evidence preparation, and atomic JSON contracts."""

from copy import deepcopy
from dataclasses import replace
import errno
import json
from uuid import uuid4

import pytest

from rangekeeper.io import _atomic
from rangekeeper.workflow import source_checks
from rangekeeper.workflow._contracts import Produced
from rangekeeper.workflow._table_operations import NumbersSpec, TransformsSpec
from rangekeeper.workflow.evidence import (
    Claim,
    Issue,
    Location,
    Severity,
    Source,
    fingerprint,
    tabular,
)
from rangekeeper.workflow.evidence.tabular import NumberSpec
from rangekeeper.workflow.evidence.transform import TransformSpec
from rangekeeper.workflow.operation import _Failure


def missing_table(codes=("fractional_count", "blank_cell", "non_numeric_value")):
    row = uuid4()
    key = ("rows", str(row), "value")
    source = Source(name="Input", checksum="review")
    claim = Claim.sourced(None, at=Location(source=source, reference={"record": "1"}))
    issues = tuple(
        Issue(
            rule_id=f"scope-{index}",
            code=code,
            message=code,
            severity=Severity.WARNING,
            at=(scope,),
            related_claims=(claim,),
        )
        for index, (code, scope) in enumerate(zip(codes, (key[:2], (), key)))
    )
    return (
        tabular.from_claims(
            name="input",
            columns=("value",),
            row_ids=(row,),
            claims={key: claim},
            issues=issues,
        ),
        source,
        key,
    )


def numeric(*names):
    return dict(
        id="quality",
        operation="numeric_issues",
        tables=[dict(table=name, columns=["value"]) for name in names],
    )


def test_produced_evidence_keeps_its_object_fingerprint_and_source_boundary():
    from rangekeeper.adapters.excel.workflow import OPERATIONS as excel_operations
    from rangekeeper.workflow._table_operations import OPERATIONS

    table, _, key = missing_table()
    result = Produced.from_evidence(table)
    assert result.value is table
    assert result.value.claims[key] is table.claims[key]
    assert result.fingerprint == fingerprint(table)
    assert result.source is None
    assert all(
        operation.describe == Produced.from_evidence
        for operation in OPERATIONS.values()
    )
    assert excel_operations["extract"].describe == Produced.from_evidence
    assert excel_operations["classify_rows"].describe == Produced.from_evidence


@pytest.mark.parametrize(
    "wrapper, policy, raw",
    [
        (NumbersSpec, NumberSpec, {"column": "source", "integer": True}),
        (
            TransformsSpec,
            TransformSpec,
            {"operation": "normalize", "columns": ["source"]},
        ),
    ],
)
def test_mapping_preparation_preserves_order_copy_and_boundary_errors(
    wrapper, policy, raw
):
    data = dict(input="input", specifications={"second": raw, "first": raw})
    before = deepcopy(data)
    request = wrapper.from_mapping(data)
    assert data == before
    assert tuple(request.specifications) == ("second", "first")
    assert all(isinstance(value, policy) for value in request.specifications.values())
    typed = dict(request.specifications)
    copied = wrapper(input="input", specifications=typed)
    typed.clear()
    assert tuple(copied.specifications) == ("second", "first")
    with pytest.raises(TypeError, match="specifications must be a mapping"):
        wrapper.from_mapping(dict(input="input", specifications=[]))
    with pytest.raises(TypeError, match=f"Expected {policy.__name__} mapping"):
        wrapper(input="input", specifications={"bad": object()})


def test_numeric_checks_prepare_each_exact_object_once_and_reprepare_next_call(
    monkeypatch,
):
    table, _, key = missing_table()
    equal_table = replace(table)
    assert equal_table == table and equal_table is not table
    original = source_checks.prepare
    visits = []

    def prepare(value):
        visits.append(value)
        prepared = original(value)
        assert prepared.evidence is value
        return prepared

    def forbidden(*args):
        raise AssertionError("numeric checks must use the prepared cell index")

    monkeypatch.setattr(source_checks, "prepare", prepare)
    monkeypatch.setattr(tabular, "issues_for", forbidden)
    declarations = (numeric("left", "alias", "equal"), numeric("alias"))
    outputs = {"left": table, "alias": table, "equal": equal_table}
    first = source_checks.evaluate(declarations, outputs)
    assert len(visits) == 2 and visits[0] is table and visits[1] is equal_table
    assert table.claims[key] is equal_table.claims[key]
    assert all(item.name == "Input: fractional count" for item in first)
    assert all(item.count == 1 for item in first)
    assert source_checks.evaluate(declarations, outputs) == first
    assert len(visits) == 4 and visits[2] is table and visits[3] is equal_table


@pytest.mark.parametrize(
    "codes, reason",
    [
        (("fractional_count", "blank_cell", "non_numeric_value"), "fractional count"),
        (("unmapped_reason", "blank_cell", "non_numeric_value"), "blank"),
        (
            ("unmapped_reason", "another_reason", "non_numeric_value"),
            "non-numeric value",
        ),
    ],
)
def test_numeric_checks_keep_scope_encounter_order_and_source_filter(codes, reason):
    table, source, key = missing_table(codes)
    result = source_checks.evaluate(
        (numeric("input"),), {"input": table}, source_ids={source.id}
    )
    assert len(result) == 1 and result[0].name == "Input: " + reason
    assert (
        source_checks.evaluate(
            (numeric("input"),), {"input": table}, source_ids={uuid4()}
        )
        == ()
    )
    # Row requests still include child-cell Issues; keep that separate contract.
    assert tabular.issues_for(table, table.data.rows[0].id) == table.issues
    assert all(
        a is b
        for a, b in zip(
            tabular.issues_for(table, table.data.rows[0].id, "value"), table.issues
        )
    )


@pytest.mark.parametrize("operation", ["identities", "occupied_rows", "numeric_issues"])
def test_empty_source_checks_reject_missing_columns_upfront(operation):
    table = tabular.from_claims(name="empty", columns=("value",), row_ids=(), claims={})
    declaration = dict(id="missing", operation=operation)
    if operation == "numeric_issues":
        declaration["tables"] = [dict(table="input", columns=["absent"])]
    else:
        declaration.update(table="input", name="missing", explanation="missing")
        declaration["column" if operation == "identities" else "columns"] = (
            "absent" if operation == "identities" else ["absent"]
        )
    with pytest.raises(_Failure) as failure:
        source_checks.evaluate((declaration,), {"input": table})
    assert failure.value.diagnostic.code == "missing_column"


@pytest.mark.parametrize("failure", [None, "sync", "interrupt"])
def test_atomic_json_keeps_encoding_and_published_error_contract(
    tmp_path, monkeypatch, failure
):
    path = tmp_path / "latest.json"
    path.write_text("old")
    value = {"name": "München", "values": [False, 0, None]}
    expected = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if failure is not None:

        def fail(_):
            if failure == "interrupt":
                raise KeyboardInterrupt("sync interrupted")
            raise OSError(errno.EIO, "sync failed")

        monkeypatch.setattr(_atomic, "_sync_directory", fail)
        error = (
            _atomic.PublishedFileInterrupted
            if failure == "interrupt"
            else _atomic.PublishedFileError
        )
        with pytest.raises(error) as caught:
            _atomic.replace_json(path, value)
        assert caught.value.path == path and caught.value.published is True
    else:
        assert _atomic.replace_json(path, value) == path
    assert path.read_text() == expected
    assert not tuple(tmp_path.glob("*.tmp"))
