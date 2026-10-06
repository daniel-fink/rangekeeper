"""Execute the complete retained design with explicit roles and independent acceptance."""

from pathlib import Path
import argparse, json, time, sys
import rangekeeper
from rangekeeper.io import json as codec, MemoryStore
from rangekeeper.model import Model
from rangekeeper.examples import design
from rangekeeper.execution import Executor
from rangekeeper.run import validate
from rangekeeper.specification import Specification


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/private/tmp/rk-turn3-private/design-solve"),
    )
    args = parser.parse_args()
    print(
        json.dumps({"python": sys.version, "package": rangekeeper.__file__}), flush=True
    )
    started = time.monotonic()

    def mark(stage):
        print(
            json.dumps(
                {
                    "stage": stage,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            ),
            flush=True,
        )

    source = codec.read("/private/tmp/rk-turn3-private/design-model.json", kind=Model)
    mark("loaded")
    root = source.find_entities(
        classification=design.classification_id(source, "property")
    )[0].id
    utilities = {
        u.id: ("plant" if u.name == "plinthplant" else "cores")
        for u in source.system.entities
        if u.name in ("plinthplant", "buildingAcores", "buildingBcores")
    }
    model = design.author(source, root=root, utility_kinds=utilities)
    mark("authored")
    model = design.formulate(model)
    mark("formulated")
    specification = design.specify(model)
    mark("specified")
    # The full 36-contributor example has a declared longer acceptance budget.
    data = specification.to_data()
    data["settings"] = {"time_limit": 300}
    specification = Specification.from_data(data)
    store = MemoryStore()
    store.put(model)
    mark("stored")
    run = Executor(store).execute(specification)
    mark("executed")
    assert run.report.status.solution == "feasible", run.report.status
    validate(run, resolver=store).raise_if_invalid()
    result = store.load_model(run.record.outputs[0])
    v = design.values(result)
    assert {c.id for c in source.provenance.claims} <= {
        c.id for c in result.provenance.claims
    }
    directory = args.output
    directory.mkdir(exist_ok=True)
    codec.write(run, directory / "run.json")
    codec.write(result, directory / "model.json")
    print(
        json.dumps(
            {
                "status": "passed",
                "contributors": len(design.select_contributors(source, root=root)),
                "unknowns": len(specification.record.unknowns),
                "pv": v["pv"].quantity.magnitude,
                "units": v["pv"].quantity.units,
                "source_claims_preserved": len(source.provenance.claims),
                "output_revision": str(result.id),
            }
        )
    )


if __name__ == "__main__":
    main()
