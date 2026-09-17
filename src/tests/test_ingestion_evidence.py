"""Contract proofs; these helpers are fixtures, not a production operation API."""

import subprocess
import sys
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

import pint
import pytest

from rangekeeper.graph import (
    Classification,
    Definitions,
    Entity,
    Graph,
    Relationship,
    Taxonomy,
)
from rangekeeper.graph.adapter import csv, ingestion, pandas
from rangekeeper.graph.adapter.ingestion import (
    Evidence,
    EvidenceValidationError,
    Issue,
    IssueSeverity,
    fingerprint,
    tabular,
    validate,
)
from rangekeeper.graph.errors import IdentityConflictError
from rangekeeper.graph.provenance import Claim, Location, Method, Source
from rangekeeper.graph.table import Row, Table, TableError


def uid(key):
    return uuid5(NAMESPACE_URL, "rk-evidence-test:" + key)


def sourced(source, key, value):
    return Claim.sourced(
        value,
        at=Location(source=source, reference={"cell": key}),
        id=uid("claim:" + key),
    )


def derived(key, value, *inputs, version="1"):
    return Claim.derived(
        value,
        from_claims=inputs,
        method=Method(code=key, version=version),
        id=uid("derived:" + key),
    )


def address(row="r1", column="area"):
    return ("rows", str(uid(row)), column)


def issue(
    claim, *, key=None, code="missing_formula_cache", severity=IssueSeverity.WARNING
):
    return Issue(
        rule_id="read_area",
        code=code,
        severity=severity,
        message="No cached area value",
        at=(key or address(),),
        related_claims=(claim,),
    )


def table_evidence(claim, *, issues=()):
    return tabular.from_claims(
        name="areas",
        columns=("area",),
        row_ids=(uid("r1"),),
        claims={address(): claim},
        issues=issues,
    )


@pytest.fixture
def source():
    return Source(id=uid("source"), name="Synthetic workbook", checksum="a" * 64)


def test_public_surface():
    assert ingestion.__all__ == [
        "Evidence",
        "EvidenceKey",
        "EvidenceValidationError",
        "Issue",
        "IssueSeverity",
        "fingerprint",
        "tabular",
        "validate",
    ]
    assert not hasattr(ingestion, "IssueEffect")
    assert not hasattr(ingestion, "Record")
    assert not hasattr(ingestion, "TabularData")


def test_optional_row_ids_and_normalization():
    values = {"a": 1}
    identified = Row(values=values, id=uid("r1"))
    values["a"] = 2
    assert identified.values["a"] == 1
    with pytest.raises(TypeError):
        identified.values["a"] = 2
    with pytest.raises(FrozenInstanceError):
        identified.id = uid("r2")
    plain = Table(columns=("a",), rows=({"a": 1}, {"a": 2}))
    assert all(row.id is None for row in plain.rows)
    assert not hasattr(plain, "row_ids")
    mixed = Table(columns=("a",), rows=(identified, {"a": 2}))
    assert mixed.rows[0] == identified
    assert mixed.rows[1].id is None
    assert identified != replace(identified, id=uid("r2"))
    assert Table(columns=(), rows=()).rows == ()


def test_invalid_row_ids_and_duplicate_identified_rows():
    with pytest.raises(TypeError, match="UUID"):
        Row(values={"a": 1}, id="r1")
    with pytest.raises(TableError, match="unique"):
        Table(
            columns=("a",),
            rows=(
                Row(values={"a": 1}, id=uid("r1")),
                Row(values={"a": 2}, id=uid("r1")),
            ),
        )
    # Cell columns can be named id/values without colliding with row metadata.
    row = Row(values={"id": "source-key", "values": 1}, id=uid("r1"))
    assert row.values["id"] == "source-key"
    assert row.id == uid("r1")


def test_reorder_and_filter_bundle_identity_with_values(source):
    evidence = tabular.from_claims(
        name="areas",
        columns=("area",),
        row_ids=(uid("r1"), uid("r2")),
        claims={
            address("r1"): sourced(source, "A1", 103),
            address("r2"): sourced(source, "A2", 97),
        },
    )
    reordered = replace(
        evidence, data=replace(evidence.data, rows=reversed(evidence.data.rows))
    )
    assert reordered.data.column("area") == (97, 103)
    assert reordered.data.rows[0].id == uid("r2")
    selected = replace(
        reordered,
        data=replace(reordered.data, rows=reordered.data.rows[:1]),
        claims={address("r2"): evidence.claims[address("r2")]},
    )
    assert tabular.row(selected, uid("r2")).values["area"] == 97
    assert tabular.claim(selected, uid("r2"), "area") is evidence.claims[address("r2")]
    assert evidence.data.column("area") == (103, 97)


def test_graph_projection_identity_and_arborescence_order():
    kind = Classification(id=uid("contains"), code="contains", name="Contains")
    taxonomy = Taxonomy(
        id=uid("taxonomy"), code="test", name="Test", classifications=(kind,)
    )
    root, child = (
        Entity(id=uid("root"), name="Root"),
        Entity(id=uid("child"), name="Child"),
    )
    graph = Graph(
        definitions=Definitions(taxonomies=(taxonomy,)),
        entities=(child, root),
        relationships=(
            Relationship(source_id=root.id, target_id=child.id, classification=kind),
        ),
    )
    plain = Table.from_view(graph.view(), fields=("name",))
    assert tuple(row.id for row in plain.rows) == (child.id, root.id)
    assert plain.columns == ("name",)
    tree = Table.from_arborescence(graph.view())
    assert tuple(row.id for row in tree.rows) == (root.id, child.id)
    assert tree.column("entity_id") == tuple(row.id for row in tree.rows)


def test_exports_do_not_invent_metadata_columns(tmp_path):
    original = Table(
        columns=("name",), rows=(Row(values={"name": "Apartment"}, id=uid("r1")),)
    )
    frame = pandas.to_dataframe(original)
    assert list(frame.columns) == ["name"]
    assert pandas.from_dataframe(frame).rows[0].id is None
    path = csv.write(original, tmp_path / "schedule.csv")
    assert path.read_text() == "name\nApartment\n"
    assert csv.read(path).rows[0].id is None
    assert tuple(row.id for row in original.rows) == (uid("r1"),)


@pytest.mark.parametrize(
    "value",
    [
        0,
        False,
        103,
        1.25,
        "04.01",
        uid("value"),
        date(2026, 9, 17),
        datetime(2026, 9, 17, tzinfo=timezone.utc),
        time(12, 30),
        timedelta(days=1),
        ("raw", None),
        frozenset(("a", "b")),
    ],
)
def test_supported_values(source, value):
    claim = sourced(source, "J8", value)
    evidence = table_evidence(claim)
    assert tabular.row(evidence, uid("r1")).values["area"] == value
    assert tabular.claim(evidence, uid("r1"), "area") is claim
    assert validate(evidence) is None
    assert fingerprint(evidence).startswith("sha256:")


@pytest.mark.parametrize("value", [[], {}, {1}, float("nan"), float("inf"), object()])
def test_mutable_and_unsupported_payloads_rejected(source, value):
    with pytest.raises(EvidenceValidationError, match="unsupported_value"):
        table_evidence(sourced(source, "J8", value))


def test_live_pint_rejected_without_changing_ordinary_table(source):
    quantity = 103 * pint.UnitRegistry().meter ** 2
    assert (
        Table(columns=("value",), rows=({"value": quantity},)).column("value")[0]
        is quantity
    )
    with pytest.raises(EvidenceValidationError, match="unsupported_value"):
        table_evidence(sourced(source, "J8", quantity))


def test_area_preserves_raw_and_unit_rule_evidence(source):
    raw = sourced(source, "J8", (("raw", 103), ("formula", None), ("cached", None)))
    rule = Claim.asserted(
        ("unit", "meter**2"),
        method=Method(code="declared-area-unit", version="1"),
        id=uid("rule"),
    )
    result = derived("parse_area", 103, raw, rule)
    evidence = table_evidence(result)
    assert evidence.data.column("area") == (103,)
    assert result.sources == (raw, rule)
    assert raw.sources[0].reference["cell"] == "J8"


def test_missing_formula_result_and_policy_separation(source):
    raw = sourced(source, "J8", (("formula", "=SUM(K8:L8)"), ("cached", None)))
    result = derived("cached_area", None, raw)
    with pytest.raises(EvidenceValidationError, match="unexplained_missing"):
        table_evidence(result)
    missing = issue(raw)
    evidence = table_evidence(result, issues=(missing,))
    assert evidence.data.column("area") == (None,)
    # The same Evidence can be displayed or composed without area; an operation
    # requiring a complete total must apply its own rule. No global blocking flag.
    assert not hasattr(missing, "effect")
    assert tabular.issues_for(evidence, uid("r1"), "area") == (missing,)
    error = replace(missing, severity=IssueSeverity.ERROR)
    assert table_evidence(result, issues=(error,)).data.column("area") == (None,)
    usable = sourced(source, "J9", 103)
    assert table_evidence(usable, issues=(error,)).data.column("area") == (103,)


def test_conflict_and_explicit_resolution_keep_history(source):
    first, second = sourced(source, "C8", 2), sourced(source, "D8", 3)
    unresolved = derived("compare_bedrooms", None, first, second)
    conflict = Issue(
        rule_id="compare_bedrooms",
        code="conflicting_values",
        severity=IssueSeverity.WARNING,
        message="Bedroom candidates disagree",
        at=(address(column="bedrooms"),),
        related_claims=(first, second),
    )
    before = tabular.from_claims(
        name="types",
        columns=("bedrooms",),
        row_ids=(uid("r1"),),
        claims={address(column="bedrooms"): unresolved},
        issues=(conflict,),
    )
    decision = Claim.asserted(
        2, method=Method(code="user-review", version="D-test-1"), id=uid("decision")
    )
    resolved = derived("resolve_bedrooms", 2, unresolved, decision)
    after = tabular.from_claims(
        name="types",
        columns=("bedrooms",),
        row_ids=tuple(row.id for row in before.data.rows),
        claims={address(column="bedrooms"): resolved},
    )
    assert before.data.column("bedrooms") == (None,)
    assert after.data.column("bedrooms") == (2,)
    assert after.issues == ()
    assert resolved.sources[0].sources == (first, second)
    assert fingerprint(before) != fingerprint(after)


def test_reorder_filter_and_derived_column_keep_addresses(source):
    a, b = sourced(source, "J8", 103), sourced(source, "J9", 97)
    claims = {address(): a, address("r2"): b}
    before = tabular.from_claims(
        name="areas", columns=("area",), row_ids=(uid("r1"), uid("r2")), claims=claims
    )
    ordered = tabular.from_claims(
        name="areas",
        columns=("area",),
        row_ids=reversed(tuple(row.id for row in before.data.rows)),
        claims=claims,
    )
    assert ordered.data.column("area") == (97, 103)
    assert tabular.claim(ordered, uid("r1"), "area") is a
    assert fingerprint(before) != fingerprint(ordered)
    selected = tabular.from_claims(
        name="selected",
        columns=("area",),
        row_ids=(uid("r2"),),
        claims={address("r2"): b},
    )
    selection = Claim.asserted(
        ("selected_row", str(uid("r2"))),
        method=Method(code="select_rows", version="1"),
        id=uid("selection"),
    )
    doubled = derived("double_area", 194, b, selection)
    extended = tabular.from_claims(
        name="derived",
        columns=("area", "doubled"),
        row_ids=tuple(row.id for row in selected.data.rows),
        claims={address("r2"): b, address("r2", "doubled"): doubled},
    )
    assert extended.data.rows[0].values == {"area": 97, "doubled": 194}
    assert before.data.column("area") == (103, 97)


def test_missing_and_empty_total_fixtures_have_no_complete_zero(source):
    raw = sourced(source, "J8", None)
    for row_key, code in [
        ("incomplete", "missing_required_value"),
        ("empty", "empty_selection"),
    ]:
        result = derived(row_key, None, raw)
        explanation = issue(raw, key=address(row_key), code=code)
        evidence = tabular.from_claims(
            name=row_key,
            columns=("area",),
            row_ids=(uid(row_key),),
            claims={address(row_key): result},
            issues=(explanation,),
        )
        assert evidence.data.column("area") == (None,)


def test_empty_identified_evidence_and_no_unidentified_evidence():
    empty = tabular.from_claims(name="empty", columns=("area",), row_ids=(), claims={})
    assert empty.data.rows == ()
    validate(Evidence(name="empty", data=Table(columns=("area",), rows=()), claims={}))
    with pytest.raises(EvidenceValidationError, match="missing_row_ids"):
        Evidence(
            name="missing",
            data=Table(columns=("area",), rows=({"area": 1},)),
            claims={},
        )
    with pytest.raises(EvidenceValidationError, match="missing_row_ids"):
        Evidence(
            name="mixed",
            data=Table(
                columns=("area",),
                rows=(Row(values={"area": 1}, id=uid("r1")), {"area": 2}),
            ),
            claims={},
        )


def test_claim_coverage_and_typed_value_agreement(source):
    value = sourced(source, "J8", 1)
    table = Table(columns=("area",), rows=(Row(values={"area": True}, id=uid("r1")),))
    with pytest.raises(EvidenceValidationError, match="value_mismatch"):
        Evidence(name="mismatch", data=table, claims={address(): value})
    with pytest.raises(EvidenceValidationError, match="claim_coverage"):
        tabular.from_claims(
            name="missing", columns=("area",), row_ids=(uid("r1"),), claims={}
        )
    with pytest.raises(EvidenceValidationError, match="claim_coverage"):
        Evidence(
            name="extra",
            data=replace(table, rows=(replace(table.rows[0], values={"area": 1}),)),
            claims={address(): value, address("r2"): value},
        )


def test_issue_scopes_lookup_and_frozen_collections(source):
    value = sourced(source, "J8", 103)
    details = {"note": ("one", "two")}
    whole = Issue(
        rule_id="review",
        code="unverified_cache",
        severity=IssueSeverity.INFO,
        message="Review freshness",
        at=((),),
        details=details,
    )
    row_issue = replace(whole, code="row_note", at=(("rows", str(uid("r1"))),))
    cell_issue = replace(whole, code="cell_note", at=(address(),))
    claims = {address(): value}
    evidence = tabular.from_claims(
        name="areas",
        columns=("area",),
        row_ids=(uid("r1"),),
        claims=claims,
        issues=(whole, row_issue, cell_issue),
    )
    details["note"] = "changed"
    claims.clear()
    assert whole.details["note"] == ("one", "two")
    assert len(tabular.issues_for(evidence, uid("r1"))) == 3
    assert len(tabular.issues_for(evidence, uid("r1"), "area")) == 3
    with pytest.raises(TypeError):
        evidence.claims[address()] = value
    with pytest.raises(FrozenInstanceError):
        evidence.name = "changed"
    with pytest.raises(KeyError):
        tabular.row(evidence, uid("absent"))
    with pytest.raises(KeyError):
        tabular.claim(evidence, uid("r1"), "absent")
    with pytest.raises(TypeError):
        tabular.row(evidence, str(uid("r1")))
    for key in [
        ("rows", "nonsense"),
        address(column="absent"),
        ("no",),
        ("rows", str(uid("r2"))),
    ]:
        with pytest.raises(EvidenceValidationError, match="invalid_address"):
            table_evidence(value, issues=(replace(whole, at=(key,)),))


def test_issue_identity_excludes_prose_severity_details(source):
    original = issue(sourced(source, "J8", 103))
    revised = replace(
        original,
        message="New explanation",
        severity=IssueSeverity.ERROR,
        details={"count": 20},
    )
    assert original.id == revised.id
    with pytest.raises(EvidenceValidationError, match="duplicate_issue"):
        table_evidence(original.related_claims[0], issues=(original, revised))


def test_upstream_identity_conflicts_and_cycles(source):
    raw = sourced(source, "J8", 103)
    duplicate = replace(raw)
    with pytest.raises(IdentityConflictError):
        table_evidence(derived("duplicate", 103, raw, duplicate))
    other_source = replace(source)
    with pytest.raises(IdentityConflictError):
        table_evidence(derived("sources", 200, raw, sourced(other_source, "J9", 97)))
    cycle = derived("cycle", 103, raw)
    object.__setattr__(cycle, "sources", (cycle,))
    with pytest.raises(ValueError, match="acyclic"):
        table_evidence(cycle)
    invalid_raw = sourced(source, "J10", [103])
    with pytest.raises(EvidenceValidationError, match="unsupported_value"):
        table_evidence(derived("invalid_raw", 103, invalid_raw))


def test_fingerprint_determinism_and_changed_rule_source_value(source):
    def build(source, *, version="1", value=103):
        return table_evidence(
            derived("parse", value, sourced(source, "J8", value), version=version)
        )

    first = build(source)
    assert fingerprint(first) == fingerprint(build(replace(source)))
    for changed in [
        build(source, version="2"),
        build(source, value=104),
        build(replace(source, checksum="b" * 64)),
    ]:
        assert fingerprint(first) != fingerprint(changed)
    assert tuple(row.id for row in first.data.rows) == tuple(
        row.id for row in build(source, version="2").data.rows
    )
    before = fingerprint(first)
    tabular.row(first, uid("r1"))
    tabular.claim(first, uid("r1"), "area")
    tabular.issues_for(first, uid("r1"))
    assert fingerprint(first) == before


def test_mapping_insertion_order_not_content_order(source):
    a, b = sourced(source, "J8", 103), sourced(source, "J9", 97)
    rows = (uid("r1"), uid("r2"))
    forward = tabular.from_claims(
        name="areas",
        columns=("area",),
        row_ids=rows,
        claims={address(): a, address("r2"): b},
    )
    backward = tabular.from_claims(
        name="areas",
        columns=("area",),
        row_ids=rows,
        claims={address("r2"): b, address(): a},
    )
    assert fingerprint(forward) == fingerprint(backward)


def test_native_source_property_to_table():
    @dataclass(frozen=True)
    class ObjectSnapshot:
        global_id: str
        properties: tuple[tuple[str, object], ...]

    native = ObjectSnapshot("native-001", (("NetFloorArea", 103), ("Unselected", 9)))
    source = Source(id=uid("ifc"), name="Synthetic IFC", checksum="c" * 64)
    raw = Claim.sourced(
        103,
        at=Location(
            source=source,
            reference={"GlobalId": native.global_id, "property": "NetFloorArea"},
        ),
        id=uid("ifc-property"),
    )
    projected = table_evidence(derived("property_projection", 103, raw))
    assert fingerprint(projected)
    assert projected.data.column("area") == (103,)
    assert (
        projected.claims[address()].sources[0].sources[0].reference["GlobalId"]
        == "native-001"
    )
    with pytest.raises(EvidenceValidationError, match="unsupported_content"):
        Evidence(name="unsupported", data=object(), claims={})


class UnsupportedTable(Table):
    pass


@pytest.mark.parametrize("data", [object(), UnsupportedTable(columns=(), rows=())])
def test_unsupported_content_including_table_subclasses(data):
    with pytest.raises(EvidenceValidationError, match="unsupported_content"):
        Evidence(name="unsupported", data=data, claims={})


def test_table_row_lookup_and_reordered_filtered_tables():
    identified = Row(values={"a": 103}, id=uid("r1"))
    table = Table(columns=("a",), rows=({"a": 97}, identified, {"a": 99}))
    assert table.row(uid("r1")) is table.rows[1]
    for invalid in (None, "r1", str(uid("r1")), 0):
        with pytest.raises(TypeError, match="UUID"):
            table.row(invalid)
    for candidate in (table, Table(columns=("a",), rows=())):
        with pytest.raises(KeyError):
            candidate.row(uid("missing"))
    reordered = replace(table, rows=reversed(table.rows))
    filtered = replace(reordered, rows=(reordered.row(uid("r1")),))
    assert filtered.row(uid("r1")) is filtered.rows[0]
    assert filtered.row(uid("r1")).values["a"] == 103


def test_fingerprint_and_issue_identity_match_before_refactor(source):
    available = table_evidence(derived("parse", 103, sourced(source, "J8", 103)))
    raw = sourced(source, "J9", None)
    missing = table_evidence(raw, issues=(issue(raw),))
    assert (
        fingerprint(available)
        == "sha256:2a00dac088cd731674683a5c6f77c325f259ab3de58a6e91ff7ecd4945cccd8c"
    )
    assert (
        fingerprint(missing)
        == "sha256:eb6b3d6ba2e6ac2f2e4e3e1085b39f1ae8b7a816169f0ee2ad89bd96cc2df92f"
    )
    assert (
        missing.issues[0].id
        == "I-8c5c46a5584af02759fc5464fb1a8cff7f427fa896fff50725486e3a26893150"
    )


@pytest.mark.parametrize("first", ["evidence", "validation", "fingerprint", "tabular"])
def test_public_imports_and_constructor_validation_in_fresh_process(first):
    script = f"""
import importlib
importlib.import_module('rangekeeper.graph.adapter.ingestion.' + {first!r})
from rangekeeper.graph.adapter.ingestion import Evidence, fingerprint, validate, tabular, EvidenceValidationError
from rangekeeper.graph.table import Table
assert callable(fingerprint) and callable(validate) and callable(tabular.row)
empty = Evidence(name='empty', data=Table(columns=(), rows=()), claims={{}})
assert validate(empty) is None
assert fingerprint(empty).startswith('sha256:')
try:
    Evidence(name='invalid', data=object(), claims={{}})
except EvidenceValidationError as error:
    assert error.code == 'unsupported_content'
else:
    raise AssertionError('Constructor did not validate')
"""
    subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
