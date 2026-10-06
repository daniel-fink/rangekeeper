"""Build a Model from XLSX evidence, author an equation, and solve in both directions.

Writes only beneath a fresh output directory. Source building is distinct from
mathematical authoring and execution; each transition uses the public boundary.
"""

from pathlib import Path
from rangekeeper.model.expression import Reference
from uuid import uuid4


def run_example(destination: Path) -> dict:
    from openpyxl import Workbook
    from rangekeeper import Model, Specification
    from rangekeeper.workflow import WorkflowSpec, run
    from rangekeeper.workflow.specification import StepSpec
    from rangekeeper.workflow.review import export
    from rangekeeper.model import (
        Update,
        System,
        Formulation,
        Binding,
        Expression,
        Constraint,
    )
    from rangekeeper.io import yaml, json, DirectoryStore
    from rangekeeper.execution import Executor
    from rangekeeper.run import validate

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    inputs = destination / "inputs"
    inputs.mkdir()
    book = Workbook()
    book.active.title = "Schedule"
    book.active["A1"] = 10
    book.save(inputs / "source.xlsx")
    steps = tuple(
        StepSpec.from_mapping(item)
        for item in [
            {
                "id": "source",
                "operation": "read",
                "files": ["source.xlsx"],
                "source_key": "area",
            },
            {
                "id": "raw",
                "operation": "extract",
                "input": "source",
                "specification": {
                    "id": "area",
                    "version": 1,
                    "sheet": "Schedule",
                    "rows": {"start": 1, "end": 1},
                    "columns": [{"name": "area", "column": "A"}],
                },
            },
            {
                "id": "numbers",
                "operation": "numbers",
                "input": "raw",
                "specifications": {"parsed_area": {"column": "area"}},
            },
        ]
    )
    spec = WorkflowSpec(
        namespace="urn:rk:workflow-scalar",
        steps=steps,
        model={
            "taxonomy": {"code": "example", "name": "Source-to-solver example"},
            "classifications": [{"code": "asset", "name": "Asset"}],
            "measures": [{"code": "area", "name": "Area", "units": "meter**2"}],
            "templates": [],
            "objects": [
                {
                    "id": "asset",
                    "kind": "entity",
                    "identity_kind": "asset",
                    "key": {"value": "A"},
                    "name": "Asset {key}",
                    "classification": "asset",
                    "measurements": [
                        {
                            "key": "net",
                            "measure": "area",
                            "binding": {"evidence": "numbers", "column": "parsed_area"},
                        },
                        {"key": "gross", "measure": "area", "binding": {"value": None}},
                    ],
                }
            ],
            "relationships": [],
            "memberships": [],
        },
        decisions={"decisions": []},
        checks={"comparisons": [], "invariants": ["fact_coverage"]},
        hashes={},
    )
    outcome = run(spec, input_root=inputs)
    if outcome.output is None:
        raise AssertionError(outcome.diagnostics)
    built = outcome.output
    export(built, destination / "workflow")
    source_model = yaml.loads(yaml.dumps(built.model), kind=Model)
    entity = source_model.system.entities[0]
    net, gross = entity.characteristics.values
    predicate = Expression(
        id=uuid4(),
        kind="binary",
        operator="equal",
        operands=(
            Expression(id=uuid4(), kind="reference", target=Reference(target=gross.id)),
            Expression(
                id=uuid4(),
                kind="binary",
                operator="add",
                operands=(
                    Expression(
                        id=uuid4(),
                        kind="reference",
                        target=Reference(target=net.id),
                    ),
                    Expression(
                        id=uuid4(),
                        kind="reference",
                        target=Reference(target=net.id),
                    ),
                ),
            ),
        ),
    )
    formulation = Formulation(
        id=uuid4(),
        code="area",
        name="Gross area is twice net area",
        bindings=(
            Binding(name="net", value=net.id),
            Binding(name="gross", value=gross.id),
        ),
        expressions=(predicate,),
        constraints=(
            Constraint(
                id=uuid4(),
                code="equation",
                name="Area equation",
                predicate=predicate.id,
            ),
        ),
    )
    model = source_model.revise(
        Update(
            system=System.from_data(
                {
                    **source_model.system.to_data(),
                    "formulations": [formulation.to_data()],
                }
            )
        )
    )
    store = DirectoryStore(destination / "revisions")
    store.put(source_model)
    store.put(model)

    def solve(input_model, assigned, quantity, unknown):
        specification = Specification.from_data(
            {
                "metadata": {"id": str(uuid4()), "schema_version": "0.6.0"},
                "model": str(input_model.id),
                "assignments": [
                    {"target": {"target": str(assigned)}, "quantity": quantity}
                ],
                "unknowns": [{"target": str(unknown)}],
            }
        )
        result = Executor(store).execute(specification)
        validate(result, resolver=store).raise_if_invalid()
        assert result.report.status.solution == "feasible", result.report.to_data()
        return result, store.load_model(result.record.outputs[0])

    forward, first = solve(model, net.id, net.quantity.to_data(), gross.id)
    inverse, second = solve(
        first, gross.id, {"magnitude": 50, "units": "meter**2"}, net.id
    )
    assert first.value(gross.id).quantity.magnitude == 20
    assert second.value(net.id).quantity.magnitude == 25
    assert second.metadata.previous == first.id
    assert all(
        s.to_data() in [v.to_data() for v in second.provenance.sources]
        for s in source_model.provenance.sources
    )
    for name, document in (
        ("forward-run", forward),
        ("forward-model", first),
        ("inverse-run", inverse),
        ("inverse-model", second),
    ):
        json.write(document, destination / (name + ".json"))
    return {
        "source_model": str(source_model.id),
        "authored_model": str(model.id),
        "forward_run": str(forward.id),
        "inverse_run": str(inverse.id),
        "forward_gross": first.value(gross.id).quantity.to_data(),
        "inverse_net": second.value(net.id).quantity.to_data(),
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = run_example(args.output)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
