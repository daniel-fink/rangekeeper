"""Review sessions use ordinary synthetic workflows, never project fixtures."""

from rangekeeper.workflow.workbench import AttemptStatus
from rangekeeper.workflow.workbench import InspectionStatus

import json
from dataclasses import replace

import pytest

from rangekeeper.workflow import workbench
from rangekeeper.workflow.review import clarification_html
from rangekeeper.workflow.reporting import usage

from .test_workflow import example, rewrite


def setup(tmp_path):
    root, docs = example(tmp_path, "equipment")
    args = {"input_root": root / "inputs", "output_root": root / "artifacts"}
    return root, docs, args


def successful(root, args):
    attempt = workbench.build(root / "spec", **args)
    assert attempt.status == AttemptStatus.COMPLETED, attempt.diagnostics
    return attempt


def test_success_snapshot_and_deterministic_repeat(tmp_path):
    root, docs, args = setup(tmp_path)
    initial = workbench.inspect(root / "spec", **args)
    assert initial.status == InspectionStatus.NOT_BUILT
    assert not args["output_root"].exists()
    events = []
    first = workbench.build(root / "spec", **args, on_progress=events.append)
    assert first.status == AttemptStatus.COMPLETED, first.diagnostics
    assert len(repr(first)) < 1000 and len(repr(initial)) < 1000
    assert {e.phase.value for e in events} >= {"workflow", "export"}
    assert workbench.inspect(root / "spec", **args).status == InspectionStatus.CURRENT
    second = successful(root, args)
    assert first.directory is not None and second.directory is not None
    assert first.directory != second.directory
    for name in (
        "model.json",
        "checks.json",
        "manifest.json",
        "review.html",
        "viewer.html",
    ):
        assert (first.directory / name).read_bytes() == (
            second.directory / name
        ).read_bytes()
    assert not any(second.changes["graph"].values())
    assert second.changes["checks"]["changed"] == 0
    old_review = clarification_html(first.result, "viewer.html")
    docs["decisions"]["decisions"][0]["text"] = "Edited after the build"
    rewrite(root, docs)
    assert workbench.inspect(root / "spec", **args).status == InspectionStatus.STALE
    assert clarification_html(first.result, "viewer.html") == old_review
    assert "Edited after the build" not in old_review


@pytest.mark.parametrize(
    "failure", ["validation", "execution", "export", "pointer", "interrupt"]
)
def test_failure_preserves_success(tmp_path, monkeypatch, failure):
    root, docs, args = setup(tmp_path)
    first = successful(root, args)
    pointer = args["output_root"] / "latest.json"
    original = pointer.read_bytes()
    if failure == "validation":
        (root / "spec/model.yaml").write_text("invalid: true")
    elif failure == "execution":
        docs["model"]["relationships"][0]["source"]["key"] = {"target": "unknown"}
        rewrite(root, docs)
    elif failure in {"export", "interrupt"}:

        def fail(result, directory):
            (directory / "model.json").write_text("partial")
            if failure == "interrupt":
                raise KeyboardInterrupt
            raise OSError("Synthetic disk failure")

        monkeypatch.setattr(workbench, "export", fail)
    else:
        original_write = workbench._atomic_json

        def fail(path, value):
            if path.name == "latest.json":
                raise OSError("Pointer failure")
            return original_write(path, value)

        monkeypatch.setattr(workbench, "_atomic_json", fail)
    if failure == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            workbench.build(root / "spec", **args)
    else:
        attempt = workbench.build(root / "spec", **args)
        assert attempt.status == AttemptStatus.FAILED and attempt.result is None
        assert attempt.directory is None and attempt.previous == first.directory
        assert "Previous successful run" in attempt._repr_html_()
    assert pointer.read_bytes() == original
    assert not list((args["output_root"] / "runs").glob(".pending-*"))
    inspected = workbench.inspect(root / "spec", **args)
    assert inspected.latest == first.directory
    assert inspected.last_attempt is not None
    assert inspected.last_attempt["status"] in {"failed", "interrupted"}


def test_input_and_implementation_freshness(tmp_path, monkeypatch):
    root, _, args = setup(tmp_path)
    successful(root, args)
    original = workbench.manifests

    def changed(*a, **kw):
        audit, semantic, identifier = original(*a, **kw)
        return {**audit, "synthetic.py": "changed"}, semantic, identifier

    with monkeypatch.context() as patch:
        patch.setattr(workbench, "manifests", changed)
        assert workbench.inspect(root / "spec", **args).status == InspectionStatus.STALE
    path = root / "inputs/schedule.xlsx"
    path.write_bytes(path.read_bytes() + b"changed")
    assert workbench.inspect(root / "spec", **args).status == InspectionStatus.STALE
    path.unlink()
    missing = workbench.inspect(root / "spec", **args)
    assert (
        missing.status == InspectionStatus.INVALID_INPUTS and missing.latest is not None
    )


def test_adapter_owns_inspection(tmp_path, monkeypatch):
    root, _, args = setup(tmp_path)
    declaration = workbench.OPERATIONS["read"]
    called = []

    def inspect(request, input_root):
        called.append(input_root)
        return {"name": "Synthetic adapter", "status": "ready", "checksum": "external"}

    monkeypatch.setitem(
        workbench.OPERATIONS, "read", replace(declaration, inspect_input=inspect)
    )
    result = workbench.inspect(root / "spec", **args)
    assert called == [args["input_root"].resolve()]
    assert result.inputs["book"]["name"] == "Synthetic adapter"


def test_trail_multiple_supporters_and_no_target(tmp_path):
    root, docs, args = setup(tmp_path)
    decision = docs["decisions"]["decisions"][0]
    identifier = decision["id"]
    docs["decisions"]["decisions"] += [
        {**decision, "id": "D-other", "text": "Second justification"},
        {
            "id": "D-pending",
            "category": "unresolved evidence",
            "status": "proposed",
            "text": "No physical occupancy evidence",
            "source": None,
            "date": None,
        },
    ]
    docs["model"]["templates"][0]["decisions"] = [identifier, "D-other"]
    docs["decisions"]["mappings"] = [
        {
            "id": "M-reported",
            "title": "Reported association",
            "status": "accepted",
            "question": "Complete physical occupancy is unknown",
            "proposal": "Keep reported association",
            "graph_structure": "Reported relationship only",
            "source": "Schedule",
            "sheet": "Schedule",
            "cells": ["B2"],
            "decisions": [identifier, "D-other"],
        }
    ]
    rewrite(root, docs)
    built = successful(root, args).result
    targets, declarations = usage(built)
    assert targets[identifier] and targets["D-other"]
    assert "D-pending" not in targets
    assert declarations["D-other"]
    html = clarification_html(built, "viewer.html")
    assert html.index("D-pending") < html.index(f'id="decision-{identifier}"')
    assert '" open><summary>D-pending' in html
    assert "Attribution not recorded" in html and "Date not recorded" in html
    assert "No supported graph target recorded" in html
    assert (
        "#select=" in html
        and "Mapping approval and evidence completeness are separate" in html
    )
    assert any(t["characteristic"].startswith("values:") for t in targets[identifier])
    manifest = json.loads((args["output_root"] / "latest.json").read_text())
    assert manifest["directory"].startswith("runs/")


def test_changed_input_during_execution_does_not_publish(tmp_path, monkeypatch):
    root, _, args = setup(tmp_path)
    first = successful(root, args)
    original_run = workbench.run

    def changed(*a, **kw):
        result = original_run(*a, **kw)
        path = root / "inputs/schedule.xlsx"
        path.write_bytes(path.read_bytes() + b"changed during run")
        return result

    monkeypatch.setattr(workbench, "run", changed)
    attempt = workbench.build(root / "spec", **args)
    assert attempt.result is None and attempt.previous == first.directory
    assert "changed during execution" in attempt.diagnostics[0]


def test_checksum_mismatch_prevents_execution(tmp_path, monkeypatch):
    root, docs, args = setup(tmp_path)
    first = successful(root, args)
    docs["sources"]["steps"][0]["checksum"] = "0" * 64
    rewrite(root, docs)

    def unexpected(*a, **kw):
        pytest.fail("Invalid input must not execute")

    monkeypatch.setattr(workbench, "run", unexpected)
    inspected = workbench.inspect(root / "spec", **args)
    assert inspected.status == InspectionStatus.INVALID_INPUTS
    attempt = workbench.build(root / "spec", **args)
    assert attempt.result is None and attempt.previous == first.directory


def test_observer_failure_changes_no_model_or_source_fingerprint(tmp_path):
    from rangekeeper.workflow import run, load

    root, _, args = setup(tmp_path)
    spec = load(root / "spec")
    first = run(spec, input_root=args["input_root"])

    def fail(event):
        raise RuntimeError("Display unavailable")

    second = run(spec, input_root=args["input_root"], on_progress=fail)
    assert first.output.model.to_data() == second.output.model.to_data()
    assert first.output.metadata["sources"] == second.output.metadata["sources"]
    assert second.diagnostics and {d.code for d in second.diagnostics} == {
        "progress_observer_failed"
    }
    attempt = workbench.build(root / "spec", **args, on_progress=fail)
    assert attempt.status == AttemptStatus.COMPLETED and attempt.diagnostics


def test_missing_measurement_keeps_descriptive_property_and_finding(tmp_path):
    from rangekeeper.model.characteristics import value
    from rangekeeper.model.content import decode

    root, docs, args = setup(tmp_path)
    docs["model"]["templates"][0]["measurements"][0]["on_unavailable"]["property"] = {
        "key": "source_size",
        "binding": {"column": "size"},
    }
    rewrite(root, docs)
    attempt = successful(root, args)
    owner = next(e for e in attempt.result.model.find_entities() if e.code == "A2")
    assert value(owner.characteristics, "size").quantity is None
    assert decode(value(owner.characteristics, "source_size").content) is None
    assert any(f.subject == str(owner.id) for f in attempt.result.findings)
