"""Run the declared valuation examples and retain authentic immutable evidence.

Use a fresh output directory. Inputs remain the existing synthetic authoring
fixtures; output Models and Runs are produced by the actual library executor.
No fixture expected-output document is read or copied as an execution result.
"""

import argparse
import json
from pathlib import Path
from uuid import UUID, uuid4

from rangekeeper import Model, Specification
from rangekeeper.execution import Executor
from rangekeeper.io import DirectoryStore, yaml, json as codec
from rangekeeper.run import validate
from rangekeeper.specification import SpecificationRecord


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(
            "output must be a fresh or empty directory; previous evidence is immutable"
        )
    store = DirectoryStore(args.output / "revisions")
    model = yaml.read(args.examples / "model.yaml", kind=Model)
    store.put(model)
    specifications = {}
    for name in (
        "specification-common",
        "specification-composed-forward",
        "specification-composed-inverse",
    ):
        specification = yaml.read(args.examples / f"{name}.yaml", kind=Specification)
        store.put(specification)
        specifications[name] = specification
    executor = Executor(store)
    forward_spec = specifications["specification-composed-forward"]
    forward = executor.execute(forward_spec)
    if forward.report.status.solution != "feasible":
        raise RuntimeError(forward.report)
    first = store.load_model(forward.record.outputs[0])

    common = specifications["specification-common"]
    data = common.to_data()
    data["metadata"].update(
        id=str(uuid4()),
        previous=str(common.id),
        name="Shared requirements on the accepted forward output",
    )
    data["model"] = str(first.id)
    revised_common = common.revise(SpecificationRecord.from_data(data))
    store.put(revised_common)
    inverse_spec = specifications["specification-composed-inverse"]
    data = inverse_spec.to_data()
    data["metadata"].update(
        id=str(uuid4()),
        previous=str(inverse_spec.id),
        name="Inverse investigation of the accepted forward output",
    )
    data["includes"] = [str(revised_common.id)]
    revised_inverse = inverse_spec.revise(SpecificationRecord.from_data(data))
    inverse = executor.execute(revised_inverse)
    if inverse.report.status.solution != "feasible":
        raise RuntimeError(inverse.report)
    second = store.load_model(inverse.record.outputs[0])
    batch_spec = Specification.from_data(
        {
            "metadata": {
                "id": str(uuid4()),
                "schema_version": "0.4.0",
                "name": "Sequential scalar investigations",
            },
            "cases": [str(forward_spec.id), str(revised_inverse.id)],
        }
    )
    batch = executor.execute(batch_spec)
    for name, document in (
        ("run-forward", forward),
        ("model-forward", first),
        ("run-inverse", inverse),
        ("model-inverse", second),
        ("run-batch", batch),
    ):
        codec.write(document, args.output / f"{name}.json")
    for run in (forward, inverse, batch):
        validate(run, resolver=store).raise_if_invalid()
    capital = UUID("a947d40b-d9b0-54cb-a2a4-f8f598405ac2")
    rent = UUID("e3fb1434-5371-5bcb-b0b8-e3af2bf65022")
    noi = UUID("9324f928-cfc8-50bb-ba99-fe8c02a6dbd2")
    quantities = {
        "forward_capital_value": first.value(capital).quantity.to_data(),
        "forward_noi": first.value(noi).quantity.to_data(),
        "inverse_rent": second.value(rent).quantity.to_data(),
        "inverse_noi": second.value(noi).quantity.to_data(),
    }
    for key, expected in (
        ("forward_capital_value", 11000000),
        ("forward_noi", 550000),
        ("inverse_rent", 27500),
        ("inverse_noi", 500000),
    ):
        assert abs(quantities[key]["magnitude"] - expected) < 1e-6, key
    assert second.metadata.previous == first.id and first.metadata.previous == model.id
    assert (
        batch.report.status.completion == "completed" and len(batch.record.spawns) == 2
    )
    summary = {
        "input_model": str(model.id),
        "forward_run": str(forward.id),
        "forward_output": str(first.id),
        "inverse_run": str(inverse.id),
        "inverse_output": str(second.id),
        "batch_run": str(batch.id),
        "batch_children": [str(id) for id in batch.record.spawns],
        "batch_outputs": [str(id) for id in batch.record.outputs],
        "quantities": quantities,
        "implementations": [
            item.to_data() for item in forward.report.runtime.implementations
        ],
        "started_at": forward.report.runtime.started_at,
        "finished_at": inverse.report.runtime.finished_at,
        "scope": "Actual affine feasibility solves with independent candidate acceptance; no uniqueness or optimality claim.",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
