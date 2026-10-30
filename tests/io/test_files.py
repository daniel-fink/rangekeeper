"""One-call document files: rk.io.load and rk.io.save (#295, G26).

A file holds one document with its kind and the documents that it depends on.
A loaded Specification keeps its Model and the other documents, so ``solve``
resolves them.
"""

import importlib.util
import json
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.io import DirectoryStore, MemoryStore
from rangekeeper.model import Metadata
from rangekeeper.run import (
    CompletionStatus,
    Diagnostic,
    Report,
    RunRecord,
    RunStatus,
    Severity,
    SolutionStatus,
)
from rangekeeper.schema.records import Specification as SpecificationRecord
from rangekeeper.shared.errors import (
    DecodeError,
    MissingReferenceError,
    RevisionConflictError,
)
from tests.execution.lesson02 import MODEL, back, q
from tests.market.test_paths import histories

EXECUTION = all(importlib.util.find_spec(name) for name in ("pyomo", "highspy"))
needs_execution = pytest.mark.skipif(
    not EXECUTION, reason="requires the optional execution extra"
)


def synthetic(specification: rk.Specification) -> rk.Run:
    """Return a failed Run of a Specification; no backend runs."""
    return rk.Run(
        RunRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
            specification=specification.id,
            report=Report(
                status=RunStatus(
                    completion=CompletionStatus.FAILED,
                    solution=SolutionStatus.NOT_ASSESSED,
                ),
                diagnostics=(
                    Diagnostic(
                        severity=Severity.ERROR,
                        code="unsupported_capability",
                        message="Synthetic: no backend was invoked.",
                    ),
                ),
            ),
        )
    )


def test_a_model_round_trips_and_its_file_is_a_store_envelope(tmp_path):
    path = rk.io.save(document=MODEL, path=tmp_path / "feasibility.model.json")
    assert path == tmp_path / "feasibility.model.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"kind", "document"}
    assert data["kind"] == "Model"
    loaded = rk.io.load(path=path)
    assert isinstance(loaded, rk.Model)
    assert loaded.to_data() == MODEL.to_data()
    # A file of a DirectoryStore is a document file too.
    store = DirectoryStore(tmp_path / "store")
    store.put(MODEL)
    assert rk.io.load(path=store.root / f"{MODEL.id}.json").id == MODEL.id


def test_market_paths_round_trip(tmp_path):
    paths = histories()
    path = rk.io.save(document=paths, path=tmp_path / "histories.paths.json")
    assert set(json.loads(path.read_text())) == {"kind", "document"}
    loaded = rk.io.load(path=path)
    assert isinstance(loaded, rk.market.Paths)
    assert loaded == paths


def test_a_specification_brings_the_model_that_it_pins(tmp_path):
    specification = back()
    path = rk.io.save(document=specification, path=str(tmp_path / "back.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert [item["kind"] for item in data["documents"]] == ["Model"]
    loaded = rk.io.load(path=str(path))
    assert isinstance(loaded, rk.Specification)
    assert loaded.to_data() == specification.to_data()
    assert loaded.model is not None and loaded.model.id == MODEL.id
    assert loaded.roles.columns == specification.roles.columns
    # A loaded Specification takes chained calls by key.
    assert loaded.fix(leverage=q("50 %")).model_id == MODEL.id


@needs_execution
def test_solve_resolves_the_documents_of_a_loaded_specification(tmp_path):
    path = rk.io.save(document=back(), path=tmp_path / "back.json")
    loaded = rk.io.load(path=path)
    outcome = rk.execution.solve(specification=loaded)
    expected = rk.execution.solve(specification=back())
    assert rk.quantity.isclose(
        actual=outcome["land_cost"], expected=expected["land_cost"]
    )


@needs_execution
def test_a_batch_brings_its_cases(tmp_path):
    batch = back().cases(cases={"low": {"leverage": q("50 %")}, "reference": {}})
    path = rk.io.save(document=batch, path=tmp_path / "cases.json")
    kinds = [item["kind"] for item in json.loads(path.read_text())["documents"]]
    assert sorted(kinds) == ["Model", "Specification", "Specification"]
    loaded = rk.io.load(path=path)
    assert loaded.case(key="low").metadata.name == "low"
    outcome = rk.execution.solve(specification=loaded)
    assert [case.key for case in outcome.cases] == ["low", "reference"]


def test_a_specification_with_includes_takes_them_from_its_resolver(tmp_path):
    included = back()
    store = MemoryStore()
    store.put(MODEL)
    store.put(included)
    record = SpecificationRecord.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "model": str(MODEL.id),
            "includes": [str(included.id)],
        }
    )
    including = rk.Specification(record=record, model=MODEL, resolver=store)
    path = rk.io.save(document=including, path=tmp_path / "including.json")
    loaded = rk.io.load(path=path)
    assert loaded.resolver.load_specification(included.id).id == included.id
    detached = rk.Specification(record=record, model=MODEL)
    with pytest.raises(MissingReferenceError, match="pass resolver="):
        rk.io.save(document=detached, path=tmp_path / "detached.json")
    rk.io.save(document=detached, path=tmp_path / "given.json", resolver=store)
    assert not (tmp_path / "detached.json").exists()


def test_a_run_takes_its_dependencies_from_the_resolver(tmp_path):
    specification = back()
    run = synthetic(specification)
    with pytest.raises(MissingReferenceError, match="pass resolver="):
        rk.io.save(document=run, path=tmp_path / "run.json")
    store = MemoryStore()
    store.put(MODEL)
    store.put(specification)
    path = rk.io.save(document=run, path=tmp_path / "run.json", resolver=store)
    loaded = rk.io.load(path=path)
    assert isinstance(loaded, rk.Run)
    assert loaded.to_data() == run.to_data()


def test_save_makes_folders_and_never_replaces_another_document(tmp_path):
    specification = back()
    path = tmp_path / "paths" / "deeper" / "back.json"
    assert rk.io.save(document=specification, path=path) == path
    text = path.read_text()
    # The same document again: the file stays as it was.
    assert rk.io.save(document=specification, path=path) == path
    assert path.read_text() == text
    with pytest.raises(RevisionConflictError):
        rk.io.save(document=back(), path=path)
    with pytest.raises(RevisionConflictError):
        rk.io.save(document=MODEL, path=path)
    assert path.read_text() == text


def test_save_takes_documents_only(tmp_path):
    with pytest.raises(TypeError):
        rk.io.save(document=MODEL.to_data(), path=tmp_path / "data.json")  # type: ignore[arg-type]


def write(path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def entry(document) -> dict:
    return {"kind": type(document).__name__, "document": document.to_data()}


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"kind": "Model"},
        {**entry(MODEL), "extra": 1},
        {"kind": "Graph", "document": {}},
        {"kind": 1, "document": {}},
        {**entry(MODEL), "documents": []},
        {**entry(MODEL), "documents": {}},
        {**entry(MODEL), "documents": [{"kind": "Model"}]},
        {"kind": "Model", "document": []},
    ],
)
def test_text_that_is_not_a_document_file_raises_decode_error(tmp_path, data):
    path = tmp_path / "file.json"
    write(path, data)
    with pytest.raises(DecodeError):
        rk.io.load(path=path)


def test_a_file_holds_exactly_the_documents_that_its_document_needs(tmp_path):
    specification = back()
    path = tmp_path / "file.json"
    write(path, entry(specification))
    with pytest.raises(MissingReferenceError):
        rk.io.load(path=path)
    other = rk.Model(name="Other")
    write(path, {**entry(specification), "documents": [entry(MODEL), entry(other)]})
    with pytest.raises(DecodeError, match="does not depend on"):
        rk.io.load(path=path)
    write(path, {**entry(MODEL), "documents": [entry(MODEL)]})
    with pytest.raises(DecodeError, match="does not depend on"):
        rk.io.load(path=path)


def test_a_document_file_is_checked_as_the_codecs_check_it(tmp_path):
    path = tmp_path / "file.json"
    path.write_text('{"kind": "Model", "kind": "Model", "document": {}}')
    with pytest.raises(DecodeError):
        rk.io.load(path=path)
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(DecodeError):
        rk.io.load(path=path)
    with pytest.raises(FileNotFoundError):
        rk.io.load(path=tmp_path / "missing.json")
