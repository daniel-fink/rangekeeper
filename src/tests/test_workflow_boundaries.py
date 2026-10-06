"""Standalone contracts at the format/workflow boundary, independent of Mandarin."""

import subprocess
import sys
from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

import pytest

from rangekeeper import operation
from rangekeeper.adapters import excel
from rangekeeper.adapters.errors import AdapterEncodingError
from rangekeeper.evidence import Claim, Location, Method, Source, locations
from rangekeeper.workflow import source_checks
from rangekeeper.workflow.checking import evaluate, validate_checks
from rangekeeper.workflow.composition import compose
from rangekeeper.workflow.implementation import manifests, semantic_digest
from rangekeeper.workflow.ingestion import Issue, IssueSeverity, tabular
from rangekeeper.workflow.ingestion.predicates import Predicate, select_where
from rangekeeper.workflow.ingestion.transform import TransformSpec, transform
from rangekeeper.workflow.specification import StepSpec

METHOD = Method(code="synthetic", version="1")
UID = uuid5(NAMESPACE_URL, "boundary-row")
KEY = ("rows", str(UID), "value")


def evidence(value, issues=()):
    claim = Claim.asserted(value, method=METHOD, id=uuid5(UID, "claim"))
    return tabular.from_claims(
        name="sample",
        columns=("value",),
        row_ids=(UID,),
        claims={KEY: claim},
        issues=issues,
    )


@pytest.mark.parametrize("kind", ["numbers", "transform", "classify"])
def test_settings_content_and_ancestors_affect_identity(kind):
    settings = Claim.asserted("first", method=METHOD, id=uuid5(UID, "settings"))
    changed = replace(settings, value="second")
    book = native_book()
    raw = excel.extract_table(book, extraction()).output
    if kind == "numbers":
        apply = lambda s: tabular.numbers(
            evidence(0),
            specifications={"derived": tabular.NumberSpec(column="value")},
            settings=s,
        )
    elif kind == "transform":
        apply = lambda s: transform(
            evidence("text"),
            specifications={
                "derived": TransformSpec(operation="normalize", columns=("value",))
            },
            settings=s,
        )
    else:
        apply = lambda s: excel.classify_rows(
            raw,
            book,
            specification=excel.RowClassificationSpec(
                identifier="value", pattern=".*", output="derived"
            ),
            settings=s,
        )
    a, b, repeat = apply(settings), apply(changed), apply(settings)
    assert a.output is not None and b.output is not None
    assert operation.fingerprint(a.operation) != operation.fingerprint(b.operation)
    assert operation.fingerprint(a.operation) == operation.fingerprint(repeat.operation)
    assert [c.id for k, c in a.output.claims.items() if k[-1] == "derived"] != [
        c.id for k, c in b.output.claims.items() if k[-1] == "derived"
    ]
    parent = Claim.asserted("ancestor A", method=METHOD, id=uuid5(UID, "ancestor"))
    first = Claim.derived(
        "same settings", from_claims=(parent,), method=METHOD, id=settings.id
    )
    second = Claim.derived(
        "same settings",
        from_claims=(replace(parent, value="ancestor B"),),
        method=METHOD,
        id=settings.id,
    )
    assert operation.fingerprint(apply(first).operation) != operation.fingerprint(
        apply(second).operation
    )


@pytest.mark.parametrize("kind", ["numbers", "transform"])
def test_colliding_projected_explanations_are_never_discarded(kind):
    missing = Claim.asserted(None, method=METHOD, id=uuid5(UID, "claim"))
    issues = tuple(
        Issue(
            rule_id="missing",
            code="absent",
            message=message,
            severity=IssueSeverity.WARNING,
            at=(scope,),
            related_claims=(missing,),
        )
        for message, scope in [("whole table", ()), ("specific cell", KEY)]
    )
    raw = tabular.from_claims(
        name="sample",
        columns=("value",),
        row_ids=(UID,),
        claims={KEY: missing},
        issues=issues,
    )
    if kind == "numbers":
        outcome = tabular.numbers(
            raw, specifications={"derived": tabular.NumberSpec(column="value")}
        )
    else:
        outcome = transform(
            raw,
            specifications={
                "derived": TransformSpec(operation="normalize", columns=("value",))
            },
        )
    assert outcome.output is None
    assert outcome.diagnostics[0].code == "conflicting_issue"


@pytest.mark.parametrize(
    "op",
    ["workbook_health", "identities", "occupied_rows", "numeric_issues", "deferred"],
)
def test_source_check_required_fields_fail_at_validation(op):
    with pytest.raises(ValueError, match=r"source_checks\[0\].*Missing fields"):
        source_checks.validate([{"id": "bad", "operation": op}], {})


@pytest.mark.parametrize(
    "kind",
    [
        "value",
        "column",
        "evidence",
        "table_count",
        "table_keys",
        "table_total",
        "model_total",
        "model_value",
        "membership_keys",
    ],
)
def test_operand_required_fields_fail_at_validation(kind):
    with pytest.raises(ValueError, match="Missing fields"):
        validate_checks(
            {
                "comparisons": [
                    {
                        "id": "bad",
                        "group": "sample",
                        "scope": "all",
                        "left": {"kind": kind},
                        "right": {"kind": "value", "value": 1},
                    }
                ]
            },
            {},
        )


@pytest.mark.parametrize(
    "op",
    ["read", "extract", "classify_rows", "numbers", "transform", "select", "concat"],
)
def test_step_required_fields_have_declaration_path(op):
    with pytest.raises(ValueError, match="steps.bad.*Missing fields"):
        StepSpec.from_mapping({"id": "bad", "operation": op})


def test_predicates_preserve_zero_and_claim_identity():
    raw = evidence(0)
    yes = select_where(
        raw, predicate=Predicate.from_mapping({"column": "value", "equals": 0})
    ).output
    no = select_where(
        raw, predicate=Predicate.from_mapping({"column": "value", "equals": False})
    ).output
    assert yes.claims[KEY] is raw.claims[KEY]
    assert no.data.rows == ()
    unavailable = select_where(raw, predicate=Predicate("absent", (0,)))
    assert unavailable.output is None
    assert unavailable.diagnostics[0].code == "missing_column"


def native_book(extra=None):
    source = Source(id=uuid5(UID, "book"), name="Fixture", checksum="fixture")
    cells = {
        "A1": excel.Cell(
            location=Location(source=source, reference={"sheet": "Data", "cell": "A1"}),
            raw="item",
        ),
        "A2": excel.Cell(
            location=Location(source=source, reference={"sheet": "Data", "cell": "A2"}),
            raw="END",
        ),
    }
    if extra:
        cells["A3"] = excel.Cell(
            location=Location(source=source, reference={"sheet": "Data", "cell": "A3"}),
            **extra,
        )
    sheet = excel.Worksheet(
        location=Location(source=source, reference={"sheet": "Data"}),
        state="visible",
        declared_rows=3,
        declared_columns=1,
        cells=cells,
    )
    return excel.Workbook(
        source=source, worksheets=(sheet,), reader_fingerprint="fixture", metadata={}
    )


def extraction():
    return excel.ExtractionSpec.from_mapping(
        {
            "id": "test",
            "version": 1,
            "sheet": "Data",
            "rows": {"start": 1, "stop_before": {"column": "A", "equals": "END"}},
            "columns": [{"name": "value", "column": "A"}],
        }
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"raw": "END", "data_type": "e"},
        {"formula": "=A2", "cached": "END", "cache_present": False},
    ],
)
def test_uniqueness_uses_native_error_and_cache_rules(extra):
    assert (
        excel.extract_table(native_book(extra), extraction(), unique_stop=True).output
        is not None
    )
    duplicate = excel.extract_table(
        native_book({"raw": "END"}), extraction(), unique_stop=True
    )
    assert duplicate.output is None
    assert duplicate.diagnostics[0].code == "nonunique_stopping_marker"


def test_uniqueness_covers_column_before_extraction_start():
    spec = replace(
        extraction(),
        rows=excel.Rows(
            start=2, stop_before=excel.StopBefore(column="A", equals="END")
        ),
    )
    book = native_book({"raw": "END"})
    assert excel.extract_table(book, spec, unique_stop=True).output is None


@pytest.mark.parametrize(
    "content", ["a: &a 1\nb: *a", "a: 1\na: 2", "a: !!python/name:os.system ''"]
)
def test_both_yaml_entrypoints_reject_unsafe_or_ambiguous_content(content):
    from rangekeeper._yaml import decode

    with pytest.raises(ValueError):
        decode(content)
    with pytest.raises(AdapterEncodingError):
        excel.load_specification(content)


@pytest.mark.parametrize(
    "computation_path", ["workflow/composition.py", "_behaviors/flow.py"]
)
def test_semantic_identity_ignores_prose_but_tracks_executable_changes(
    tmp_path, computation_path
):
    assert semantic_digest('"""one"""\nx = 1 # a') == semantic_digest(
        '"""two"""\nx = 1 # b'
    )
    assert semantic_digest("x = 1") != semantic_digest("x = 2")
    (tmp_path / "workflow").mkdir(parents=True)
    computation = tmp_path / computation_path
    computation.parent.mkdir(parents=True, exist_ok=True)
    renderer = tmp_path / "workflow/review.py"
    computation.write_text('"""first"""\nx = 1')
    renderer.write_text("x = 1")
    audit, semantic, identity = manifests(tmp_path)
    renderer.write_text("x = 2")
    computation.write_text('"""second"""\nx = 1')
    next_audit, next_semantic, next_identity = manifests(tmp_path)
    assert (
        audit != next_audit and semantic == next_semantic and identity == next_identity
    )
    computation.write_text("x = 2")
    assert manifests(tmp_path)[2] != identity


def test_excel_import_does_not_load_workflow_runner():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from rangekeeper.adapters import excel; assert 'rangekeeper.workflow.runtime' not in sys.modules; assert 'rangekeeper.workflow.specification' not in sys.modules",
        ],
        check=True,
    )


def test_direct_composition_and_checking_without_workflow_spec():
    model = {
        "taxonomy": {"code": "assets", "name": "Assets"},
        "classifications": [{"code": "machine", "name": "Machine"}],
        "measures": [],
        "templates": [],
        "objects": [
            {
                "id": "press",
                "kind": "entity",
                "classification": "machine",
                "name": "Press {key}",
                "identity_kind": "machine",
                "key": {"value": "P1"},
            }
        ],
        "relationships": [],
        "memberships": [],
    }
    settings = Claim.asserted("reviewed structure", method=METHOD)
    invocation = operation.Operation(method=METHOD, specification=model, inputs={})
    graph, findings, keys = compose(
        model, {}, settings, {}, invocation, namespace="urn:factory"
    )
    assert len(graph.system.entities) == 1 and findings == ()
    checks = evaluate(
        {
            "comparisons": [
                {
                    "id": "count",
                    "group": "inventory",
                    "scope": "all",
                    "left": {"kind": "model_count"},
                    "right": {"kind": "value", "value": 1},
                }
            ]
        },
        graph,
        keys,
        {},
    )
    assert checks[0].status == "agree"
    assert all(graph.entity(f.target).id == f.target for f in graph.provenance.facts)


def test_generic_locations_preserve_shared_ancestors():
    source = Source(name="Data", checksum="data")
    loc = Location(source=source, reference={"record": "1"})
    parent = Claim.sourced(1, at=loc)
    left = Claim.derived(2, from_claims=(parent,), method=METHOD)
    right = Claim.derived(3, from_claims=(parent,), method=METHOD)
    final = Claim.derived(5, from_claims=(left, right), method=METHOD)
    assert locations(final) == (loc,)
