"""Portable canonical investigations, independent of an originating workspace."""

import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("pyarrow")
from rangekeeper import Model, Run, Specification
from rangekeeper.execution import execute
from rangekeeper.io import MemoryStore, yaml
from rangekeeper.io.bundle import ParquetOptions, Reader, ReadLimits, identity, write
from rangekeeper.run import SolutionStatus
from rangekeeper.schema.runtime import exact_equal
from rangekeeper.shared.errors import (
    IdentityConflictError,
    MissingReferenceError,
    ReferenceTypeError,
    RevisionConflictError,
)

FIXTURES = Path(__file__).parents[2] / "examples/schema"


def inputs():
    store = MemoryStore()
    model = yaml.read(FIXTURES / "model.yaml", kind=Model)
    common = yaml.read(FIXTURES / "specification-common.yaml", kind=Specification)
    spec = yaml.read(
        FIXTURES / "specification-composed-forward.yaml", kind=Specification
    )
    for d in (model, common, spec):
        store.put(d)
    return store, model, common, spec


def test_real_run_closure_and_further_execution(tmp_path):
    store, model, common, spec = inputs()
    run = execute(spec, store).run
    assert run.report.status.solution is SolutionStatus.FEASIBLE
    output = store.load_model(run.record.outputs[0])
    first = write(tmp_path / "bundle", output, documents=[run], resolver=store)
    reader = Reader(tmp_path / "bundle")
    assert {d.id for d in reader.documents()} == {
        model.id,
        common.id,
        spec.id,
        run.id,
        output.id,
    }
    for d in reader.documents():
        original = getattr(store, "load_" + type(d).__name__.lower())(d.id)
        assert exact_equal(d.to_data(), original.to_data())
    assert (
        reader.load_specification(spec.id).compose(resolver=reader).model_id == model.id
    )
    fresh = MemoryStore()
    reader.copy_to(fresh)
    assert reader.copy_to(fresh) == reader.copy_to(fresh)
    # A new contribution explicitly selects the result Model; the old pin is retained.
    from rangekeeper.specification import SpecificationRecord

    data = common.to_data()
    data["metadata"].update(id=str(uuid4()), previous=str(common.id))
    data["model"] = str(output.id)
    revised_common = common.revise(SpecificationRecord.from_data(data))
    fresh.put(revised_common)
    data = spec.to_data()
    data["metadata"].update(id=str(uuid4()), previous=str(spec.id))
    data["includes"] = [str(revised_common.id)]
    revised = spec.revise(SpecificationRecord.from_data(data))
    again = execute(revised, fresh).run
    assert again.report.status.solution is SolutionStatus.FEASIBLE
    second = write(
        tmp_path / "second",
        fresh.load_model(again.record.outputs[0]),
        documents=[again],
        resolver=fresh,
    )
    assert second["id"] != first["id"]
    assert Reader(tmp_path / "bundle").manifest == first
    assert (
        fresh.load_specification(spec.id).compose(resolver=fresh).model_id == model.id
    )


def test_unexecuted_composition_history_and_repacking(tmp_path):
    store, model, common, spec = inputs()
    first = write(tmp_path / "one", model, documents=[spec], resolver=store)
    second = write(
        tmp_path / "two",
        model,
        documents=[spec],
        resolver=store,
        parquet=ParquetOptions(compression="snappy", row_group_size=1),
    )
    assert first["id"] == second["id"] != identity(model)
    reader = Reader(tmp_path / "one")
    assert len(reader.documents()) == 3
    assert (
        reader.records(document=spec.id, kind="Specification")["items"][0]["kind"]
        == "Specification"
    )
    with pytest.raises(ReferenceTypeError):
        reader.load_run(spec.id)
    data = model.to_data()
    data["metadata"]["previous"] = str(uuid4())
    historic = Model.from_data(data)
    write(tmp_path / "history", historic)
    assert len(Reader(tmp_path / "history").documents()) == 1


def test_batch_includes_actual_failed_attempt_and_outputs(tmp_path):
    store, model, common, spec = inputs()
    bad = yaml.read(FIXTURES / "specification-objectives.yaml", kind=Specification)
    store.put(bad)
    batch = Specification.from_data(
        dict(
            metadata=dict(id=str(uuid4()), schema_version="1.0.0"),
            cases=[str(spec.id), str(bad.id)],
        )
    )
    run = execute(batch, store).run
    assert len(run.record.spawns) == 2
    children = [store.load_run(i) for i in run.record.spawns]
    assert any(
        r.report.status.solution is SolutionStatus.NOT_ASSESSED and not r.record.outputs
        for r in children
    )
    assert any(r.report.status.solution is SolutionStatus.FEASIBLE for r in children)
    write(tmp_path / "batch", model, documents=[run], resolver=store)
    reader = Reader(tmp_path / "batch")
    assert len([d for d in reader.documents() if isinstance(d, Run)]) == 3
    reader.copy_to(MemoryStore())


def test_missing_wrong_resolver_and_conflicting_records_fail_before_export(tmp_path):
    store, model, common, spec = inputs()
    with pytest.raises(MissingReferenceError):
        write(tmp_path / "missing", model, documents=[spec])
    assert not (tmp_path / "missing").exists()

    class Wrong:
        def load_specification(self, id):
            return spec

    with pytest.raises(IdentityConflictError):
        write(tmp_path / "wrong", model, documents=[spec], resolver=Wrong())
    changed = model.to_data()
    changed["metadata"]["name"] = "Conflicting retained revision"
    with pytest.raises(RevisionConflictError):
        write(tmp_path / "conflict", model, documents=[Model.from_data(changed)])


def test_copy_conflict_preflight_preserves_destination(tmp_path):
    store, model, common, spec = inputs()
    write(tmp_path / "bundle", model, documents=[spec], resolver=store)
    other = MemoryStore()
    data = model.to_data()
    data["metadata"]["name"] = "Conflict"
    other.put(Model.from_data(data))
    with pytest.raises(RevisionConflictError):
        Reader(tmp_path / "bundle").copy_to(other)
    with pytest.raises(MissingReferenceError):
        other.load_specification(common.id)
    assert other.load_model(model.id).metadata.name == "Conflict"


@pytest.mark.parametrize(
    "case", ["root", "digest", "duplicate", "unselected", "pin", "format"]
)
def test_manifest_cannot_rebind_or_hide_documents(tmp_path, case):
    store, model, common, spec = inputs()
    manifest = write(tmp_path / "bundle", model, documents=[spec], resolver=store)
    if case == "root":
        manifest["roots"][0]["id"] = str(uuid4())
    elif case == "digest":
        manifest["documents"][0]["digest"] = "0" * 64
    elif case == "duplicate":
        manifest["documents"].append(deepcopy(manifest["documents"][0]))
    elif case == "unselected":
        manifest["roots"] = []
    elif case == "pin":
        manifest["model"]["id"] = str(uuid4())
    elif case == "format":
        manifest["format"] = "rangekeeper.bundle/1-proposal"
    (tmp_path / "bundle/manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, MissingReferenceError, OSError)):
        Reader(tmp_path / "bundle")


def test_document_budget_and_corrupt_supporting_payload(tmp_path):
    store, model, common, spec = inputs()
    manifest = write(tmp_path / "bundle", model, documents=[spec], resolver=store)
    with pytest.raises(ValueError, match="document limit"):
        Reader(tmp_path / "bundle", limits=ReadLimits(documents=2))
    path = tmp_path / "bundle" / manifest["documents"][0]["tables"][0]["path"]
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(data)
    with pytest.raises(ValueError, match="integrity"):
        Reader(tmp_path / "bundle")
