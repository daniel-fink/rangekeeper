"""Contract tests for reusable Evidence table transformations."""

from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

import pytest

from rangekeeper.graph.adapter import operation
from rangekeeper.graph.adapter.ingestion import (
    Issue,
    IssueSeverity,
    fingerprint,
    tabular,
)
from rangekeeper.graph.provenance import Claim, Location, Method, Source


def uid(value):
    return uuid5(NAMESPACE_URL, value)


SOURCE = Source(id=uid("source"), name="fixture", checksum="a" * 64)


def evidence(values, *, prefix="a", columns=("value",)):
    source = SOURCE
    claims, issues, ids = {}, [], []
    for i, values_row in enumerate(values):
        row = uid(f"{prefix}:{i}")
        ids.append(row)
        for column, value in zip(columns, values_row, strict=True):
            key = ("rows", str(row), column)
            claim = Claim.sourced(value, at=Location(source=source), id=uid(str(key)))
            claims[key] = claim
            if value is None:
                issues.append(
                    Issue(
                        rule_id="fixture",
                        code="missing_formula_cache",
                        message="No cached value",
                        severity=IssueSeverity.ERROR,
                        at=(key,),
                        related_claims=(claim,),
                    )
                )
    return tabular.from_claims(
        name=prefix, columns=columns, row_ids=ids, claims=claims, issues=issues
    )


def test_spec_strict_and_immutable():
    raw = {"column": "a", "missing_markers": [" - ", "—", "-"]}
    spec = tabular.NumberSpec.from_mapping(raw)
    raw["missing_markers"].append("x")
    assert spec.missing_markers == ("-", "—")
    assert tabular.NumberSpec.from_mapping(spec.to_mapping()) == spec
    assert not spec.nonnegative
    for bad in (
        {"column": "a", "integer": 1},
        {"column": "a", "nonnegative": "false"},
        {"column": "a", "missing_markers": "-"},
        {"column": ""},
        {"column": "a", "extra": True},
        {},
    ):
        with pytest.raises((TypeError, ValueError)):
            tabular.NumberSpec.from_mapping(bad)


def test_numbers_meanings_lineage_and_replay():
    raw = evidence([
        (0,),
        (4.0,),
        (4.5,),
        (-1,),
        (True,),
        ("4",),
        (" — ",),
        (" ",),
        (None,),
        (10**400,),
    ])
    settings = Claim.asserted(
        "policy", id=uid("settings"), method=Method(code="test", version="1")
    )
    specs = {
        "n": tabular.NumberSpec(
            column="value", integer=True, nonnegative=True, missing_markers=("—",)
        )
    }
    result = tabular.numbers(raw, specifications=specs, settings=settings)
    out = result.output
    assert out.data.column("n") == (
        0,
        4,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        10**400,
    )
    assert type(out.data.column("n")[1]) is int
    assert out.data.column("value") == raw.data.column("value")
    for row in out.data.rows:
        source = tabular.claim(raw, row.id, "value")
        assert tabular.claim(out, row.id, "value") is source
        assert tabular.claim(out, row.id, "n").sources == (source, settings)
    missing = out.data.rows[8].id
    assert tabular.issues_for(out, missing, "n")[0].code == "missing_formula_cache"
    assert tabular.issues_for(out, missing, "n")[0].severity is IssueSeverity.ERROR
    again = tabular.numbers(raw, specifications=specs, settings=settings)
    assert fingerprint(again.output) == fingerprint(out)
    assert operation.fingerprint(again.operation) == operation.fingerprint(
        result.operation
    )
    assert tabular.numbers(
        evidence([(-1.5,)]), specifications={"n": tabular.NumberSpec(column="value")}
    ).output.data.column("n") == (-1.5,)


def test_spec_and_order_affect_identity():
    raw = evidence([(1,)])
    a = tabular.NumberSpec(column="value")
    b = tabular.NumberSpec(column="value", integer=True)
    first = tabular.numbers(raw, specifications={"x": a, "y": b})
    second = tabular.numbers(raw, specifications={"y": b, "x": a})
    assert first.output.data.columns == ("value", "x", "y")
    assert operation.fingerprint(first.operation) != operation.fingerprint(
        second.operation
    )
    assert fingerprint(first.output) != fingerprint(second.output)


def test_numeric_incompatibilities_and_empty():
    raw = evidence([(1,)])
    for specs, code in [
        ({"value": tabular.NumberSpec(column="value")}, "output_collision"),
        ({"n": tabular.NumberSpec(column="absent")}, "missing_column"),
    ]:
        result = tabular.numbers(raw, specifications=specs)
        assert result.output is None and result.diagnostics[0].code == code
    assert tabular.numbers(raw, specifications={}).output == raw
    assert tabular.numbers(
        evidence([]), specifications={"n": tabular.NumberSpec(column="value")}
    ).output.data.columns == ("value", "n")


def test_select_order_partial_scopes_and_empty():
    raw = evidence([(None, 2), (None, 4)], columns=("value", "other"))
    a, b = (r.id for r in raw.data.rows)
    multi = replace(
        raw.issues[0], at=(("rows", str(a), "value"), ("rows", str(b), "value"))
    )
    raw = replace(raw, issues=(multi,))
    result = tabular.select(raw, row_ids=(b, a), columns=("other", "value"))
    assert [r.id for r in result.output.data.rows] == [b, a]
    assert result.output.data.columns == ("other", "value")
    one = tabular.select(raw, row_ids=(b,)).output
    assert one.issues[0].at == (("rows", str(b), "value"),)
    assert one.issues[0].related_claims == multi.related_claims
    assert one.issues[0].id != multi.id
    assert tabular.claim(one, b, "value") is tabular.claim(raw, b, "value")
    assert not tabular.select(raw, columns=("other",)).output.issues
    assert not tabular.select(raw, row_ids=()).output.data.rows
    assert tabular.select(raw, columns=()).output.data.columns == ()
    for kwargs, code in [
        ({"row_ids": (a, a)}, "duplicate_selector"),
        ({"columns": ("value", "value")}, "duplicate_selector"),
        ({"row_ids": (uid("absent"),)}, "unknown_row"),
        ({"columns": ("absent",)}, "missing_column"),
    ]:
        assert tabular.select(raw, **kwargs).diagnostics[0].code == code


def test_concat_scopes_order_empty_and_diagnostics():
    left = evidence([(None,)], prefix="left")
    right = evidence([(2,)], prefix="right")
    global_issue = replace(left.issues[0], at=((),))
    left = replace(left, issues=(global_issue,))
    result = tabular.concat((left, evidence([]), right), name="combined")
    out = result.output
    assert out.data.column("value") == (None, 2)
    assert tabular.issues_for(out, left.data.rows[0].id) == out.issues
    assert not tabular.issues_for(out, right.data.rows[0].id)
    assert out.issues[0].at == (("rows", str(left.data.rows[0].id)),)
    assert tabular.claim(out, right.data.rows[0].id, "value") is tabular.claim(
        right, right.data.rows[0].id, "value"
    )
    assert (
        tabular.concat((left, left), name="bad").diagnostics[0].code == "duplicate_row"
    )
    incompatible = evidence([(1,)], columns=("different",))
    assert (
        tabular.concat((left, incompatible), name="bad").diagnostics[0].code
        == "incompatible_columns"
    )
    assert tabular.concat((evidence([]),), name="empty").output.data.rows == ()
    with pytest.raises(ValueError):
        tabular.concat((), name="empty")


def test_concat_conflicting_claim_identity_is_diagnostic():
    left = evidence([(1,)], prefix="left")
    right = evidence([(2,)], prefix="right")
    key, claim = next(iter(right.claims.items()))
    right = replace(
        right, claims={key: replace(claim, id=next(iter(left.claims.values())).id)}
    )
    result = tabular.concat((left, right), name="bad")
    assert result.output is None
    assert result.diagnostics[0].code == "conflicting_evidence"


def test_global_missing_issue_propagates_without_duplicates():
    raw = evidence([(None,)], columns=("value",))
    raw = replace(
        raw,
        issues=(
            replace(
                raw.issues[0], at=((), ("rows", str(raw.data.rows[0].id), "value"))
            ),
        ),
    )
    out = tabular.numbers(
        raw, specifications={"n": tabular.NumberSpec(column="value")}
    ).output
    assert out is not None
    assert all(
        i.code == "missing_formula_cache"
        for i in tabular.issues_for(out, raw.data.rows[0].id, "n")
    )


def test_settings_lineage_and_policy_change_affect_claim_ids():
    raw = evidence([(2,)])
    settings = Claim.asserted(
        "first", method=Method(code="settings", version="1"), id=uid("policy")
    )
    specs = {"n": tabular.NumberSpec(column="value")}
    first = tabular.numbers(raw, specifications=specs, settings=settings)
    second = tabular.numbers(
        raw, specifications=specs, settings=replace(settings, value="second")
    )
    assert first.operation.inputs["settings"] != second.operation.inputs["settings"]
    row_id = raw.data.rows[0].id
    assert (
        tabular.claim(first.output, row_id, "n").id
        != tabular.claim(second.output, row_id, "n").id
    )
    changed = tabular.numbers(
        raw,
        specifications={"n": tabular.NumberSpec(column="value", nonnegative=True)},
        settings=settings,
    )
    assert (
        tabular.claim(first.output, row_id, "n").id
        != tabular.claim(changed.output, row_id, "n").id
    )


def test_propagation_deduplicates_identical_projected_issues():
    raw = evidence([(None,)])
    issue = raw.issues[0]
    # Independent valid scopes can project to the same derived cell.
    raw = replace(raw, issues=(issue, replace(issue, at=((),))))
    out = tabular.numbers(
        raw, specifications={"n": tabular.NumberSpec(column="value")}
    ).output
    assert out is not None
    key = ("rows", str(raw.data.rows[0].id), "n")
    assert sum(i.at == (key,) for i in out.issues) == 1
    conflicting = replace(
        raw, issues=(issue, replace(issue, at=((),), message="different explanation"))
    )
    outcome = tabular.numbers(
        conflicting, specifications={"n": tabular.NumberSpec(column="value")}
    )
    assert outcome.output is None and outcome.diagnostics[0].code == "conflicting_issue"


def test_warnings_do_not_decide_numeric_availability():
    raw = evidence([(3,)])
    warning = Issue(
        rule_id="review",
        code="uncertain",
        severity=IssueSeverity.ERROR,
        message="Review source",
        at=((),),
    )
    raw = replace(raw, issues=(warning,))
    out = tabular.numbers(
        raw, specifications={"n": tabular.NumberSpec(column="value")}
    ).output
    assert out.data.column("n") == (3,)
    assert out.issues[0] is warning


def test_concat_preserves_input_order_and_replay():
    first = evidence([(1,)], prefix="first")
    second = evidence([(2,)], prefix="second")
    ab = tabular.concat((first, second), name="combined")
    ba = tabular.concat((second, first), name="combined")
    assert ba.output.data.column("value") == (2, 1)
    assert operation.fingerprint(ab.operation) != operation.fingerprint(ba.operation)
    assert fingerprint(ab.output) == fingerprint(
        tabular.concat((first, second), name="combined").output
    )


def test_selection_preserves_global_and_row_issues():
    raw = evidence([(1,), (2,)])
    first, second = (row.id for row in raw.data.rows)
    global_issue = Issue(
        rule_id="review",
        code="uncertain",
        severity=IssueSeverity.WARNING,
        message="Review source",
        at=((),),
    )
    row_issue = replace(global_issue, at=(("rows", str(first)),))
    raw = replace(raw, issues=(global_issue, row_issue))
    out = tabular.select(raw, row_ids=(second,)).output
    assert out.issues == (global_issue,)
    assert out.issues[0] is global_issue
    assert fingerprint(out) == fingerprint(
        tabular.select(raw, row_ids=(second,)).output
    )
