"""Finalized Run construction, exact resolution and publication preconditions."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import uuid4, UUID

import pytest
import yaml

import rangekeeper as rk
from rangekeeper.errors import (
    ValidationError,
    UnsupportedVersionError,
    MissingReferenceError,
)
from rangekeeper.io import MemoryStore
from rangekeeper.run import Run, RunRecord, validate

EXAMPLES = Path(__file__).resolve().parents[2] / "schema/examples"


def load(name):
    return yaml.safe_load((EXAMPLES / (name + ".yaml")).read_text())


def inputs():
    store = MemoryStore()
    for pattern, kind in (
        ("model*.yaml", rk.Model),
        ("specification*.yaml", rk.Specification),
    ):
        for path in EXAMPLES.glob(pattern):
            store.put(kind.from_data(yaml.safe_load(path.read_text())))
    return store


@pytest.mark.parametrize("name", ["forward", "inverse", "failed", "skipped", "batch"])
def test_local_run_snapshots_are_immutable_and_do_not_execute(name):
    data = load("run-" + name)
    run = Run.from_data(data)
    assert run.id == UUID(data["metadata"]["id"])
    assert isinstance(run.record, RunRecord)
    with pytest.raises(FrozenInstanceError):
        run.metadata = None
    with pytest.raises(AttributeError):
        run.report.status.completion = "failed"
    detached = run.to_data()
    detached["report"].clear()
    data["metadata"]["name"] = "changed"
    assert run.to_data()["report"] and run.metadata.name != "changed"
    assert not hasattr(run, "revise")


@pytest.mark.parametrize(
    "change",
    [
        "status",
        "output",
        "duplicate_spawn",
        "self_spawn",
        "predecessor",
        "diagnostic",
        "runtime",
        "timing",
        "trace",
    ],
)
def test_local_run_rejects_inconsistent_evidence(change):
    data = load("run-forward")
    if change == "status":
        data["report"]["status"]["completion"] = "failed"
    elif change == "output":
        data.pop("outputs")
    elif change == "duplicate_spawn":
        data["spawns"] = [str(uuid4())] * 2
    elif change == "self_spawn":
        data["spawns"] = [data["metadata"]["id"]]
    elif change == "predecessor":
        data["metadata"]["previous"] = data["metadata"]["id"]
    elif change == "diagnostic":
        data = load("run-failed")
        data["report"].pop("diagnostics")
    elif change == "runtime":
        data["report"].pop("runtime")
    elif change == "timing":
        data["report"]["runtime"].update(
            started_at="2026-10-02T02:00:00Z", finished_at="2026-10-02T01:00:00Z"
        )
    else:
        data["report"]["trace"] = [
            {"kind": "validation", "message": "late", "at": "2026-10-02T20:00:00Z"}
        ]
    with pytest.raises(ValidationError):
        Run.from_data(data)


def test_run_version_is_checked_without_resolving_external_documents():
    data = load("run-failed")
    data["metadata"]["schema_version"] = "999"
    with pytest.raises(UnsupportedVersionError):
        Run.from_data(data)


def test_real_store_resolves_all_synthetic_fixture_trees():
    store = inputs()
    for name in ("forward", "inverse", "failed", "skipped", "batch"):
        run = Run.from_data(load("run-" + name))
        assert validate(run, resolver=store).valid
        assert store.put(run) == run.id
        assert store.put(run) == run.id
        assert store.load_run(run.id).to_data() == run.to_data()


def test_missing_output_rejects_publication_without_partial_run():
    store = inputs()
    data = load("run-forward")
    data["outputs"] = [str(uuid4())]
    # Drop publication/diagnostic references to the original output too.
    data["report"]["trace"] = []
    data["report"]["diagnostics"] = []
    run = Run.from_data(data)
    assert validate(run, resolver=store).issues[0].code == "reference.missing"
    with pytest.raises(ValidationError):
        store.put(run)
    with pytest.raises(MissingReferenceError):
        store.load_run(run.id)


def test_failed_attempt_can_reference_an_incomplete_saved_specification():
    store = MemoryStore()
    spec = rk.Specification.from_data(
        {"metadata": {"id": str(uuid4()), "schema_version": "0.4.0"}}
    )
    store.put(spec)
    run = Run.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "0.1.0"},
            "specification": str(spec.id),
            "report": {
                "status": {"completion": "failed", "solution": "not_assessed"},
                "diagnostics": [
                    {
                        "severity": "error",
                        "code": "specification_invalid",
                        "message": "No input Model was supplied.",
                    }
                ],
            },
        }
    )
    assert validate(run, resolver=store).valid
    store.put(run)


@pytest.mark.parametrize(
    "problem,code", [("kind", "reference.kind"), ("identity", "reference.identity")]
)
def test_resolver_results_must_match_requested_kind_and_revision(problem, code):
    class WrongResolver:
        def load_specification(self, identity):
            if problem == "kind":
                return rk.Model.from_data(
                    {"metadata": {"id": str(identity), "schema_version": "0.3.0"}}
                )
            return rk.Specification.from_data(
                {"metadata": {"id": str(uuid4()), "schema_version": "0.4.0"}}
            )

        def load_model(self, identity):
            raise MissingReferenceError(str(identity))

        def load_run(self, identity):
            raise MissingReferenceError(str(identity))

    assert (
        validate(Run.from_data(load("run-failed")), resolver=WrongResolver())
        .issues[0]
        .code
        == code
    )


def test_spawn_cycle_is_detected_without_infinite_resolution():
    store = inputs()
    a = load("run-failed")
    b = deepcopy(a)
    b["metadata"]["id"] = str(uuid4())
    a["spawns"] = [b["metadata"]["id"]]
    b["spawns"] = [a["metadata"]["id"]]
    root, child = Run.from_data(a), Run.from_data(b)

    class Resolver:
        load_model = store.load_model
        load_specification = store.load_specification

        def load_run(self, identity):
            return {root.id: root, child.id: child}[identity]

    report = validate(root, resolver=Resolver())
    assert not report.valid and "cycle" in report.issues[0].message


def test_scoped_report_documents_resolve_outside_the_input_tree():
    store = inputs()
    extra = rk.Model.from_data(
        {"metadata": {"id": str(uuid4()), "schema_version": "0.3.0"}}
    )
    store.put(extra)
    data = load("run-failed")
    data["report"]["diagnostics"][0].update(
        document=str(extra.id), target=str(extra.id)
    )
    assert validate(Run.from_data(data), resolver=store).valid
    data["report"]["diagnostics"][0]["target"] = str(uuid4())
    assert not validate(Run.from_data(data), resolver=store).valid
