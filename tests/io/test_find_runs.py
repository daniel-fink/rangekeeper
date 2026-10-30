"""``find_runs`` finds stored Runs by the name of their Specification (#294).

The Runs come in the order of their recorded finish times, the same for each
store; a batch Run takes the latest time of its cases.
"""

from pathlib import Path
from uuid import UUID, uuid4

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
from rangekeeper.schema.records import Implementation, ImplementationKind, Runtime
from rangekeeper.shared.errors import ContractError
from rangekeeper.specification import SpecificationRecord
from tests.execution.test_pipeline import dated


@pytest.fixture(params=["memory", "directory"])
def store(request, tmp_path):
    if request.param == "memory":
        return MemoryStore()
    return DirectoryStore(path=tmp_path / "records")


def named(model: rk.Model, name: str) -> rk.Specification:
    return rk.Specification(
        record=SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0", name=name),
            model=model.id,
        )
    )


def failed(
    specification: rk.Specification,
    *,
    id: UUID,
    finished: str | None = None,
) -> rk.Run:
    """Return a synthetic failed Run; with ``finished``, it records that time."""
    report: dict = {
        "status": RunStatus(
            completion=CompletionStatus.FAILED, solution=SolutionStatus.NOT_ASSESSED
        ),
        "diagnostics": (
            Diagnostic(
                severity=Severity.ERROR,
                code="unsupported_capability",
                message="Synthetic example: no execution backend was invoked.",
            ),
        ),
    }
    if finished is not None:
        report["runtime"] = Runtime(
            started_at=finished,
            finished_at=finished,
            implementations=(
                Implementation(
                    kind=ImplementationKind.SOLVER, name="synthetic", version="1"
                ),
            ),
        )
    return rk.Run(
        RunRecord(
            metadata=Metadata(id=id, schema_version="1.0.0"),
            specification=specification.id,
            report=Report(**report),
        )
    )


def test_an_empty_store_finds_no_runs(store):
    assert store.find_runs(specification="Base case") == ()


def test_runs_come_in_the_order_of_their_finish_times(store):
    model = rk.Model.create(metadata=Metadata(id=uuid4(), schema_version="1.0.0"))
    specification = named(model, "Named")
    other = named(model, "Other")
    for document in (model, specification, other):
        store.put(document)
    # The UUID order and the order of the puts are not the order of the times.
    late = failed(specification, id=UUID(int=1), finished="2027-01-01T10:00:00Z")
    early = failed(specification, id=UUID(int=2), finished="2027-01-01T09:00:00Z")
    unknown = failed(specification, id=UUID(int=3))
    elsewhere = failed(other, id=UUID(int=4), finished="2027-01-01T11:00:00Z")
    for run in (late, early, unknown, elsewhere):
        store.put(run)
    found = store.find_runs(specification="Named")
    assert [run.id for run in found] == [unknown.id, early.id, late.id]
    assert all(isinstance(run, rk.Run) for run in found)
    assert [run.id for run in store.find_runs(specification="Other")] == [elsewhere.id]
    assert store.find_runs(specification="named") == ()


def test_a_batch_run_takes_the_latest_time_of_its_cases(store):
    pytest.importorskip("pyomo")
    pytest.importorskip("highspy")
    batch = dated().cases(cases={"low": {"rate": "5 % pa"}, "high": {"rate": "9 % pa"}})
    first = rk.execution.execute(specification=batch, store=store)
    second = rk.execution.execute(specification=batch, store=store)
    found = store.find_runs(specification="Dated")
    assert [run.id for run in found] == [first.run.id, second.run.id]
    assert found[-1].to_data() == second.run.to_data()
    cases = store.find_runs(specification="low")
    assert [run.id for run in cases] == [
        first.case(key="low").run.id,
        second.case(key="low").run.id,
    ]


def test_find_runs_takes_a_name(store):
    with pytest.raises(TypeError, match="specification"):
        store.find_runs(specification=uuid4())
    with pytest.raises(ContractError, match="specification"):
        store.find_runs(specification=" ")
    with pytest.raises(TypeError):
        store.find_runs("Named")  # type: ignore[misc]


def test_a_directory_store_skips_files_that_are_not_revisions(tmp_path):
    store = DirectoryStore(path=tmp_path)
    model = rk.Model.create(metadata=Metadata(id=uuid4(), schema_version="1.0.0"))
    specification = named(model, "Named")
    run = failed(specification, id=uuid4(), finished="2027-01-01T09:00:00Z")
    for document in (model, specification, run):
        store.put(document)
    (tmp_path / f".{run.id}.json.abc.tmp").write_text("partial", encoding="utf-8")
    (tmp_path / "notes.json").write_text("{}", encoding="utf-8")
    assert [found.id for found in store.find_runs(specification="Named")] == [run.id]


def test_a_directory_store_takes_its_path_as_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = DirectoryStore(path="runs/03")
    assert store.root == Path.cwd() / "runs" / "03"
    assert not store.root.exists()  # construction creates nothing
