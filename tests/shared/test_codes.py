"""Codes and structured fields of diagnostics (ADR-016)."""

from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.errors import Code
from rangekeeper.schema import validation as structure
from rangekeeper.shared.diagnostics import Issue
from rangekeeper.shared.errors import ContractError
from rangekeeper.shared.validation import bounded, require


def test_codes_are_public_strings_with_their_wire_values():
    assert rk.errors.Code is Code
    assert Code.UNIQUE == "semantic.unique"
    assert Code("structure.required") is Code.STRUCTURE_REQUIRED


def test_issue_holds_a_code_and_read_only_fields():
    target = uuid4()
    issue = Issue("semantic.units", "text", targets=[target], values={"units": "m"})
    assert issue.code is Code.UNITS
    assert issue.targets == (target,)
    with pytest.raises(TypeError):
        issue.values["units"] = "ft"  # type: ignore[index]
    with pytest.raises(ValueError):
        Issue("semantic.unknown", "text")


def test_contract_fields_reach_the_reported_issue():
    target, document = uuid4(), uuid4()

    def check():
        require(
            False,
            "text",
            code=Code.REFERENCE_KIND,
            path="/a",
            targets=(target,),
            values={"actual": "Formulation"},
            evidence={"count": 2},
        )

    (issue,) = bounded([], check, document={"metadata": {"id": str(document)}}).issues
    assert (issue.code, issue.document_id, issue.path) == (
        Code.REFERENCE_KIND,
        document,
        "/a",
    )
    assert issue.targets == (target,)
    assert dict(issue.values) == {"actual": "Formulation"}
    assert dict(issue.evidence) == {"count": 2}
    error = ContractError.from_issue(issue).at("/b")
    assert (error.code, error.path, error.targets) == (
        Code.REFERENCE_KIND,
        "/b",
        (target,),
    )


def test_a_schema_keyword_without_a_member_keeps_its_name_as_a_field():
    assert structure._structure_code("required") is Code.STRUCTURE_REQUIRED
    assert structure._structure_code("dynamicRef") is Code.STRUCTURE
