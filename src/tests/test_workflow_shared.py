"""Named policies reuse declarations without changing execution or source meaning."""

from copy import deepcopy
from dataclasses import replace

import pytest

from rangekeeper.graph.adapter import json as graph_json
from rangekeeper.graph.provenance import locations
from rangekeeper.graph.workflow import load, run, schema
from rangekeeper.graph.workflow._shared import resolve_measurements
from rangekeeper.graph.workflow.review import export

from .test_workflow import example, rewrite


def shared_example(tmp_path):
    root, docs = example(tmp_path, "equipment")
    numeric = docs["sources"]["steps"][4]
    docs["sources"]["number_sets"] = {"sizes": numeric.pop("specifications")}
    numeric["specifications_ref"] = "sizes"
    item = docs["model"]["templates"][0]
    docs["model"]["measurement_sets"] = {"readings": item.pop("measurements")}
    item["measurements_ref"] = "readings"
    rewrite(root, docs)
    return root, docs


def test_named_sets_match_inline_and_remain_auditable(tmp_path):
    root, docs = example(tmp_path, "equipment")
    inline = load(root / "spec")
    numeric = docs["sources"]["steps"][4]
    docs["sources"]["number_sets"] = {"sizes": numeric.pop("specifications")}
    numeric["specifications_ref"] = "sizes"
    item = docs["model"]["templates"][0]
    docs["model"]["measurement_sets"] = {"readings": item.pop("measurements")}
    item["measurements_ref"] = "readings"
    rewrite(root, docs)
    shared = load(root / "spec")
    assert shared.steps == inline.steps
    assert shared.model == inline.model
    # Equal configuration identity isolates execution equivalence from the
    # deliberately different authored-document fingerprints.
    equivalent = replace(shared, hashes=inline.hashes, declarations={})
    a = run(inline, input_root=root / "inputs").output
    b = run(equivalent, input_root=root / "inputs").output
    assert graph_json.dumps(a.graph) == graph_json.dumps(b.graph)
    assert a.checks == b.checks
    real = run(shared, input_root=root / "inputs").output
    repeat = run(load(root / "spec"), input_root=root / "inputs").output
    assert graph_json.dumps(real.graph) == graph_json.dumps(repeat.graph)
    assert real.metadata == repeat.metadata
    assert real.checks == a.checks
    assert real.findings == a.findings
    assert [m["measure"] for m in shared.model["templates"][0]["measurements"]] == [
        "size",
        "count",
    ]
    assert real.evidence["numeric"].data.columns[-1] == "number_size"
    assert real.evidence["numeric"].data.rows[0].values["number_size"] == 0
    assert real.evidence["numeric"].data.rows[1].values["number_size"] is None
    assert shared.declarations["uses"][0]["definition"] == "sources.number_sets.sizes"
    assert all(
        any(
            loc.source.name == "workflow specification"
            for c in f.claims
            for loc in locations(c)
        )
        for f in real.graph.provenance.facts
    )
    export(real, root / "output")
    assert "effective_specification" in (root / "output/manifest.json").read_text()
    assert (
        "Shared declarations and effective specification"
        in (root / "output/review.html").read_text()
    )
    with pytest.raises(TypeError):
        shared.declarations["number_sets"]["sizes"]["number_size"]["column"] = "changed"


@pytest.mark.parametrize(
    "case",
    [
        "unknown_numbers",
        "both_numbers",
        "wrong_operation",
        "unused_bad_numbers",
        "unknown_measurements",
        "both_measurements",
        "unused_bad_measurements",
        "nested_reference",
        "duplicate_measure",
        "unknown_decision",
        "unknown_context",
        "orphan_context",
        "null_context",
        "no_row_context",
    ],
)
def test_invalid_shared_declarations_fail_during_load(tmp_path, case):
    root, docs = shared_example(tmp_path)
    sources, model = docs["sources"], docs["model"]
    step, item = sources["steps"][4], model["templates"][0]
    if case == "unknown_numbers":
        step["specifications_ref"] = "absent"
    elif case == "both_numbers":
        step["specifications"] = {}
    elif case == "wrong_operation":
        step["operation"] = "transform"
    elif case == "unused_bad_numbers":
        sources["number_sets"]["unused"] = {"bad": {"column": "size", "integer": 1}}
    elif case == "unknown_measurements":
        item["measurements_ref"] = "absent"
    elif case == "both_measurements":
        item["measurements"] = []
    elif case == "unused_bad_measurements":
        model["measurement_sets"]["unused"] = [
            {"measure": "absent", "binding": {"column": "size"}}
        ]
    elif case == "nested_reference":
        model["measurement_sets"]["readings"] = {"measurements_ref": "readings"}
    elif case == "duplicate_measure":
        model["measurement_sets"]["readings"].append(
            deepcopy(model["measurement_sets"]["readings"][0])
        )
    elif case == "unknown_decision":
        model["measurement_sets"]["readings"][0]["decisions"] = ["absent"]
    elif case == "unknown_context":
        item["measurements_evidence"] = "absent"
    elif case == "orphan_context":
        item.pop("measurements_ref")
        item["measurements_evidence"] = "total"
    elif case == "null_context":
        item["measurements_evidence"] = None
    else:
        item.pop("table")
        item["key"] = {"value": "one"}
    rewrite(root, docs)
    with pytest.raises(
        (ValueError, TypeError), match="(set|measurements|specifications)"
    ):
        load(root / "spec")


def test_context_rebinding_is_explicit_and_does_not_mutate_definitions(tmp_path):
    _root, docs = shared_example(tmp_path)
    model = docs["model"]
    binding = {"column": "number"}
    model["measurement_sets"]["readings"] = [
        {
            "measure": "size",
            "binding": binding,
            "when": {"binding": {"column": "number"}, "available": True},
            "evidence": [{"column": "number"}, {"evidence": "items", "column": "size"}],
            "on_unavailable": {"feature": "missing", "binding": {"column": "number"}},
        }
    ]
    model["templates"][0]["measurements_evidence"] = "total"
    original = deepcopy(model)
    resolved, _ = resolve_measurements(
        model, {"items": "table", "total": "table"}, docs["decisions"]
    )
    assert model == original
    reading = resolved["templates"][0]["measurements"][0]
    assert reading["binding"]["evidence"] == "total"
    assert reading["when"]["binding"]["evidence"] == "total"
    assert reading["on_unavailable"]["binding"]["evidence"] == "total"
    assert reading["evidence"] == [
        {"column": "number", "evidence": "total"},
        {"evidence": "items", "column": "size"},
    ]
    reading["binding"]["column"] = "changed"
    assert model == original


@pytest.mark.parametrize("context,available", [("total", True), ("levels", False)])
def test_named_context_uses_existing_single_row_contract(tmp_path, context, available):
    root, docs = shared_example(tmp_path)
    docs["model"]["measurement_sets"]["readings"] = [
        {"measure": "size", "binding": {"column": "number"}}
    ]
    docs["model"]["templates"][0]["measurements_evidence"] = context
    rewrite(root, docs)
    result = run(load(root / "spec"), input_root=root / "inputs")
    if available:
        assert result.output is not None
        items = [
            e for e in result.output.graph.entities if e.classification.code == "item"
        ]
        assert all(e.measurements["size"].quantity.magnitude == 12 for e in items)
    else:
        assert result.output is None
        assert result.diagnostics[0].code == "ambiguous_evidence"


def test_shared_policy_edit_updates_only_declared_consumers(tmp_path):
    root, docs = shared_example(tmp_path)
    docs["sources"]["steps"].append({
        "id": "second_numeric",
        "operation": "numbers",
        "input": "selected",
        "specifications_ref": "sizes",
    })
    rewrite(root, docs)
    before = load(root / "spec")
    docs["sources"]["number_sets"]["sizes"]["number_size"]["nonnegative"] = False
    rewrite(root, docs)
    after = load(root / "spec")
    changed = [a.id for a, b in zip(before.steps, after.steps) if a != b]
    assert changed == ["numeric", "second_numeric"]
    assert after.model == before.model
    assert after.steps[4].request.specifications["number_size"].nonnegative is False


def test_shared_schema_and_duplicate_inline_measurements(tmp_path):
    catalog = schema()
    assert "specifications_ref" in catalog["operations"]["numbers"]["properties"]
    assert "number_sets" in catalog["shared_declarations"]
    root, docs = example(tmp_path)
    attrs = docs["model"]["templates"][0]["measurements"]
    attrs.append(deepcopy(attrs[0]))
    rewrite(root, docs)
    with pytest.raises(ValueError, match="Duplicate measurement"):
        load(root / "spec")
