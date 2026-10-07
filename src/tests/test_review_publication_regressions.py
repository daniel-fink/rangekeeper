"""Independent regressions for review findings at evidence and publication seams."""

from dataclasses import replace
import errno
import json
from pathlib import Path
from uuid import uuid4

import pytest

from rangekeeper.evidence import Claim, Location, Source, tabular
from rangekeeper.evidence.transform import TransformSpec, transform
from rangekeeper.io import _atomic
from rangekeeper.workflow import implementation, workbench
from rangekeeper.workflow.specification import load

from .test_workbench import setup, successful


@pytest.mark.parametrize("operation", ("numbers", "transform"))
@pytest.mark.parametrize("settings_case", ("same", "equal", "content", "lineage"))
def test_derivation_preserves_settings_identity_conflicts(operation, settings_case):
    source = Source(name="Input", checksum="edition-a")
    original = Claim.sourced("12", at=Location(source=source, reference={"cell": "A1"}))
    settings = original
    if settings_case == "equal":
        settings = replace(original)
    elif settings_case == "content":
        settings = replace(original, value="different configuration")
    elif settings_case == "lineage":
        settings = replace(
            original,
            sources=(
                Location(
                    source=replace(source, checksum="edition-b"),
                    reference={"cell": "A1"},
                ),
            ),
        )
    row = uuid4()
    evidence = tabular.from_claims(
        name="input",
        columns=("raw",),
        row_ids=(row,),
        claims={("rows", str(row), "raw"): original},
    )
    if operation == "numbers":
        outcome = tabular.numbers(
            evidence,
            specifications={"derived": tabular.NumberSpec(column="raw")},
            settings=settings,
        )
    else:
        outcome = transform(
            evidence,
            specifications={
                "derived": TransformSpec(operation="normalize", columns=("raw",))
            },
            settings=settings,
        )
    if settings_case == "same":
        assert outcome.output is not None, outcome.diagnostics
        derived = outcome.output.claims[("rows", str(row), "derived")]
        assert len(derived.sources) == 1 and derived.sources[0] is original
    else:
        assert outcome.output is None
        assert outcome.diagnostics[0].code == "conflicting_evidence"
        assert str(original.id) in outcome.diagnostics[0].message


@pytest.mark.parametrize("replace_existing", (False, True))
def test_atomic_error_identifies_file_visible_after_failed_directory_sync(
    tmp_path, monkeypatch, replace_existing
):
    path = tmp_path / "output.json"
    if replace_existing:
        path.write_text("old")

    def fail(_):
        raise OSError(errno.EIO, "directory fsync failed")

    monkeypatch.setattr(_atomic, "_sync_directory", fail)
    write = _atomic.replace if replace_existing else _atomic.write_new
    with pytest.raises(OSError) as caught:
        write(path, "new")
    assert path.read_text() == "new"
    assert caught.value.published is True
    assert caught.value.path == path
    assert "durability" in str(caught.value)
    assert not tuple(tmp_path.glob("*.tmp"))


def test_atomic_failure_before_replacement_preserves_old_file(tmp_path, monkeypatch):
    path = tmp_path / "latest.json"
    path.write_text("old")

    def fail(*_):
        raise OSError(errno.EIO, "replacement failed")

    monkeypatch.setattr(_atomic.os, "replace", fail)
    with pytest.raises(OSError) as caught:
        _atomic.replace(path, "new")
    assert not getattr(caught.value, "published", False)
    assert path.read_text() == "old"
    assert not tuple(tmp_path.glob("*.tmp"))
    with pytest.raises(FileExistsError):
        _atomic.write_new(path, "new")
    assert path.read_text() == "old"


def test_workbench_retains_new_visible_result_when_pointer_sync_fails(
    tmp_path, monkeypatch
):
    # Isolate publication from other agents' source edits; fingerprint contracts
    # have separate tests and the build still executes the real workflow.
    monkeypatch.setattr(workbench, "manifests", lambda *a, **k: ({}, {}, "fixed"))
    root, _, args = setup(tmp_path)
    first = successful(root, args)
    pointer = args["output_root"] / "latest.json"
    old = pointer.read_bytes()
    sync = _atomic._sync_directory

    def fail_after_publication(parent):
        if parent == args["output_root"] and pointer.read_bytes() != old:
            raise OSError(errno.EIO, "directory fsync failed")
        return sync(parent)

    monkeypatch.setattr(_atomic, "_sync_directory", fail_after_publication)
    result = workbench.build(root / "spec", **args)
    assert result.status is workbench.AttemptStatus.COMPLETED
    assert result.result is not None and result.directory is not None
    assert result.previous == first.directory and result.directory != first.directory
    assert (
        args["output_root"] / json.loads(pointer.read_text())["directory"]
        == result.directory
    )
    assert any("durability" in message for message in result.diagnostics)
    assert (
        json.loads((args["output_root"] / "latest-attempt.json").read_text())["status"]
        == "completed"
    )


def test_jsonschema_version_changes_workflow_identity_and_metadata(
    tmp_path, monkeypatch
):
    root, _, _ = setup(tmp_path)
    spec = load(root / "spec")
    modules, dependencies = implementation.capabilities(spec)
    package = tmp_path / "package"
    package.mkdir()
    current = implementation.version
    before = implementation.manifests(
        package, modules=modules, dependencies=dependencies
    )
    monkeypatch.setattr(
        implementation,
        "version",
        lambda name: "999.review" if name == "jsonschema" else current(name),
    )
    after = implementation.manifests(
        package, modules=modules, dependencies=dependencies
    )
    assert before[:2] == after[:2]
    assert before[2] != after[2]
    assert "jsonschema" in dependencies
    metadata = implementation.metadata(spec, {}, (), (), {}, {}, dependencies)
    assert metadata["dependencies"]["jsonschema"] == "999.review"


def test_workbench_status_record_failure_keeps_completed_publication(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(workbench, "manifests", lambda *a, **k: ({}, {}, "fixed"))
    root, _, args = setup(tmp_path)
    first = successful(root, args)
    write = workbench._atomic_json

    def fail_status(path, value):
        if path.name == "latest-attempt.json":
            raise OSError(errno.EIO, "attempt record failed")
        return write(path, value)

    monkeypatch.setattr(workbench, "_atomic_json", fail_status)
    result = workbench.build(root / "spec", **args)
    assert result.status is workbench.AttemptStatus.COMPLETED
    assert result.result is not None and result.directory != first.directory
    assert any("attempt record failed" in message for message in result.diagnostics)
    pointer = json.loads((args["output_root"] / "latest.json").read_text())
    assert args["output_root"] / pointer["directory"] == result.directory


@pytest.mark.parametrize(
    "failure", ("before_replace", "directory_sync", "attempt_record")
)
def test_layout_publication_reports_visibility_and_durability(
    tmp_path, monkeypatch, failure
):
    from rangekeeper.adapters.cytoscape.layout import review
    from .test_layout_workbench import fixture

    graph, profile, output, _, _ = fixture(tmp_path)
    args = {"bundle": graph.directory, "profile": profile, "output_root": output}
    first = review.build(graph.result.model, **args)
    assert first.status is review.BuildStatus.COMPLETED
    pointer = output / "latest.json"
    original = pointer.read_bytes()
    actual_replace, actual_sync = _atomic.os.replace, _atomic._sync_directory

    def replace_fault(source, destination):
        target = Path(destination)
        if (
            failure == "before_replace"
            and target == pointer
            or failure == "attempt_record"
            and target == output / "latest-attempt.json"
        ):
            raise OSError(errno.EIO, failure)
        return actual_replace(source, destination)

    def sync_fault(parent):
        if (
            failure == "directory_sync"
            and parent == output
            and pointer.read_bytes() != original
        ):
            raise OSError(errno.EIO, "directory sync failed")
        return actual_sync(parent)

    monkeypatch.setattr(_atomic.os, "replace", replace_fault)
    monkeypatch.setattr(
        Path, "replace", lambda path, target: replace_fault(path, target)
    )
    monkeypatch.setattr(_atomic, "_sync_directory", sync_fault)
    result = review.build(graph.result.model, **args)
    assert result.diagnostics
    if failure == "before_replace":
        assert result.status is review.BuildStatus.FAILED and result.directory is None
        assert result.previous == first.directory
        assert pointer.read_bytes() == original
    else:
        assert result.status is review.BuildStatus.COMPLETED
        assert result.directory is not None and result.directory != first.directory
        assert output / json.loads(pointer.read_text())["run"] == result.directory
        assert result.measurements
        assert any(
            ("durability" if failure == "directory_sync" else "attempt_record")
            in message
            for message in result.diagnostics
        )


@pytest.mark.parametrize("caller", ("workflow", "layout"))
def test_published_attempt_keeps_its_result_without_overwriting_a_later_pointer(
    tmp_path, monkeypatch, caller
):
    if caller == "workflow":
        monkeypatch.setattr(workbench, "manifests", lambda *a, **k: ({}, {}, "fixed"))
        root, _, args = setup(tmp_path)
        output = args["output_root"]
        build = lambda: workbench.build(root / "spec", **args)
    else:
        from rangekeeper.adapters.cytoscape.layout import review
        from .test_layout_workbench import fixture

        graph, profile, output, _, _ = fixture(tmp_path)
        build = lambda: review.build(
            graph.result.model,
            bundle=graph.directory,
            profile=profile,
            output_root=output,
        )
    first = build()
    assert first.status.value == "completed"
    pointer = output / "latest.json"
    older = pointer.read_bytes()
    sync = _atomic._sync_directory
    raced = False

    def competing_writer(parent):
        nonlocal raced
        if parent == output and not raced and pointer.read_bytes() != older:
            raced = True
            # A later writer chooses the earlier complete run. The current
            # attempt must neither overwrite that choice nor adopt its result.
            pointer.write_bytes(older)
            raise OSError(errno.EIO, "directory sync failed after another writer")
        return sync(parent)

    monkeypatch.setattr(_atomic, "_sync_directory", competing_writer)
    result = build()
    assert raced and result.status.value == "completed"
    assert result.directory is not None and result.directory != first.directory
    assert pointer.read_bytes() == older
    assert any("durability" in message for message in result.diagnostics)


@pytest.mark.parametrize(
    "caller,phase",
    (
        ("workflow", "observer"),
        ("workflow", "status"),
        ("workflow", "persistent_status"),
        ("workflow", "sync"),
        ("layout", "status"),
        ("layout", "persistent_status"),
        ("layout", "sync"),
    ),
)
def test_interruption_after_publication_preserves_completed_evidence(
    tmp_path, monkeypatch, caller, phase
):
    from rangekeeper.workflow.progress import ProgressPhase, ProgressStatus

    def observer(event):
        if (
            phase == "observer"
            and event.phase is ProgressPhase.EXPORT
            and event.status is ProgressStatus.COMPLETED
        ):
            raise KeyboardInterrupt("completion observer interrupted")

    if caller == "workflow":
        monkeypatch.setattr(workbench, "manifests", lambda *a, **k: ({}, {}, "fixed"))
        root, _, args = setup(tmp_path)
        output, module = args["output_root"], workbench
        first = successful(root, args)
        build = lambda: workbench.build(root / "spec", **args, on_progress=observer)
        pointer_key = "directory"
    else:
        from rangekeeper.adapters.cytoscape.layout import review
        from .test_layout_workbench import fixture

        graph, profile, output, _, _ = fixture(tmp_path)
        module = review
        build = lambda: review.build(
            graph.result.model,
            bundle=graph.directory,
            profile=profile,
            output_root=output,
        )
        first = build()
        pointer_key = "run"
    pointer = output / "latest.json"
    previous = pointer.read_bytes()
    write, sync = module._atomic_json, _atomic._sync_directory
    interrupted = False

    def write_status(path, value):
        nonlocal interrupted
        if (
            path.name == "latest-attempt.json"
            and phase in {"status", "persistent_status"}
            and (not interrupted or phase == "persistent_status")
        ):
            interrupted = True
            raise KeyboardInterrupt("status write interrupted")
        return write(path, value)

    def sync_pointer(parent):
        nonlocal interrupted
        if (
            phase == "sync"
            and parent == output
            and pointer.read_bytes() != previous
            and not interrupted
        ):
            interrupted = True
            raise KeyboardInterrupt("directory sync interrupted")
        return sync(parent)

    monkeypatch.setattr(module, "_atomic_json", write_status)
    monkeypatch.setattr(_atomic, "_sync_directory", sync_pointer)
    with pytest.raises(KeyboardInterrupt) as caught:
        build()
    completed = caught.value.completed_attempt
    assert completed.status.value == "completed"
    assert completed.directory is not None and completed.directory != first.directory
    assert output / json.loads(pointer.read_text())[pointer_key] == completed.directory
    status = json.loads((output / "latest-attempt.json").read_text())
    assert status["status"] == "completed"
    if phase == "persistent_status":
        assert any("not confirmed" in message for message in completed.diagnostics)
    else:
        assert Path(status["directory"]) in (
            completed.directory,
            completed.directory.relative_to(output),
        )
    assert completed.diagnostics
