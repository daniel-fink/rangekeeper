"""Finite Movement equations checked against an independent temporal oracle."""

from rangekeeper.model.expression import ValueReference
from dataclasses import replace
from datetime import date
from uuid import uuid4
import math
import json as std_json
from pathlib import Path
import sys
from rangekeeper.io import DirectoryStore, json as codec

from rangekeeper.model import (
    Model,
    Metadata,
    Definitions,
    System,
    Entity,
    Characteristics,
    Value,
    Measure,
    Quantity,
    Update,
)
from rangekeeper.model.flow import Flow, Movement
from rangekeeper.duration.period import make_periods
from rangekeeper.formulations import flow, growth, financial
from rangekeeper.specification import Specification, SpecificationRecord, Assignment
from rangekeeper.specification.targets import (
    scalar,
    movement,
    assign_flow,
    unknown_flow,
)
from rangekeeper.execution import Executor
from rangekeeper.io import MemoryStore
from rangekeeper.run import validate


def oracle():
    ids = {name: uuid4() for name in ("initial", "rate", "cash", "discounted", "pv")}
    money, ratio = uuid4(), uuid4()
    periods = make_periods(date(2027, 1, 1), frequency="year", count=3)
    values = [
        Value(id=ids[name], key=name, kind="measurement", measure=measure)
        for name, measure in [("initial", money), ("rate", ratio), ("pv", money)]
    ]
    for name in ("cash", "discounted"):
        values.append(
            Value(
                id=ids[name],
                key=name,
                kind="flow",
                measure=money,
                flow=Flow(
                    units="AUD",
                    movements=tuple(
                        Movement(key=f"y{i+1}", period=p) for i, p in enumerate(periods)
                    ),
                ),
            )
        )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
        definitions=Definitions(
            measures=(
                Measure(id=money, code="money", name="Money", units="AUD"),
                Measure(id=ratio, code="ratio", name="Ratio", units="dimensionless"),
            )
        ),
        system=System(
            entities=(
                Entity(
                    id=uuid4(), characteristics=Characteristics(values=tuple(values))
                ),
            )
        ),
    )
    equations = (
        growth.build_compound(
            model,
            id=uuid4(),
            initial=scalar(ids["initial"]),
            rate=scalar(ids["rate"]),
            result=ids["cash"],
        ),
        financial.build_discount(
            model,
            id=uuid4(),
            source=ids["cash"],
            rate=scalar(ids["rate"]),
            result=ids["discounted"],
        ),
        financial.build_present_value(
            model, id=uuid4(), source=ids["discounted"], result=scalar(ids["pv"])
        ),
    )
    data = model.system.to_data()
    data["formulations"] = [f.to_data() for f in equations]
    return model.revise(Update(system=System.from_data(data))), ids


def investigate(model, ids, *, inverse=False):
    fixed = "pv" if inverse else "initial"
    unknown = "initial" if inverse else "pv"
    return Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
            model=model.id,
            assignments=(
                Assignment(
                    target=scalar(ids[fixed]),
                    quantity=Quantity(magnitude=300 if inverse else 100, units="AUD"),
                ),
                Assignment(
                    target=scalar(ids["rate"]),
                    quantity=Quantity(magnitude=0.1, units="dimensionless"),
                ),
            ),
            unknowns=(
                scalar(ids[unknown]),
                *unknown_flow(model, ids["cash"]),
                *unknown_flow(model, ids["discounted"]),
            ),
        )
    )


if __name__ == "__main__":
    import rangekeeper

    assert "/site/rangekeeper/" in rangekeeper.__file__, rangekeeper.__file__
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=False)
    store = DirectoryStore(destination / "records")
    model, ids = oracle()
    store.put(model)
    forward = Executor(store).execute(investigate(model, ids))
    assert forward.report.status.solution == "feasible", forward.report
    output = store.load_model(forward.record.outputs[0])
    assert math.isclose(output.value(ids["pv"]).quantity.magnitude, 3000 / 11)
    inverse = Executor(store).execute(investigate(output, ids, inverse=True))
    assert inverse.report.status.solution == "feasible", inverse.report
    revised = store.load_model(inverse.record.outputs[0])
    assert math.isclose(revised.value(ids["initial"]).quantity.magnitude, 110)
    validate(forward, resolver=store).raise_if_invalid()
    validate(inverse, resolver=store).raise_if_invalid()
    for name, document in [
        ("input", model),
        ("forward-run", forward),
        ("forward-output", output),
        ("inverse-run", inverse),
        ("inverse-output", revised),
    ]:
        codec.write(document, destination / (name + ".json"))
    summary = dict(
        import_path=rangekeeper.__file__,
        forward_pv=output.value(ids["pv"]).quantity.magnitude,
        inverse_initial=revised.value(ids["initial"]).quantity.magnitude,
        ids={k: str(v) for k, v in ids.items()},
    )
    (destination / "summary.json").write_text(std_json.dumps(summary, indent=2))
    print(std_json.dumps(summary))

    from rangekeeper.examples import investment
    from rangekeeper.scenarios import make_plan, generate, replay

    scenario_base = Model.create(metadata=Metadata(id=uuid4(), schema_version="0.5.0"))
    plan = make_plan(
        periods=make_periods(date(2021, 1, 1), frequency="year", count=4), seed=23
    )
    scenario = generate(scenario_base, plan, scenario_keys=("installed-proof",))[0]
    assert replay(scenario.model).model is scenario.model
    canonical = investment.formulate(
        investment.author({"num_periods": 3, "growth_rate": 0.0}, scenario=scenario)
    )
    policy = investment.build_stop_gain_resale_policy(
        canonical, threshold=1.01, minimum_holding_periods=1
    )
    policy_spec = investment.specify(canonical, policy=policy)
    store.put(canonical)
    policy_run = Executor(store).execute(policy_spec)
    assert policy_run.report.status.solution == "feasible", policy_run.report
    validate(policy_run, resolver=store).raise_if_invalid()
    policy_output = store.load_model(policy_run.record.outputs[0])
    controlled = investment.values(policy_output)
    assert sum(m.magnitude for m in controlled["sale"].flow.movements) == 1
    for name, document in [
        ("scenario", scenario.model),
        ("policy-model", canonical),
        ("policy-specification", policy_spec),
        ("policy-run", policy_run),
        ("policy-output", policy_output),
    ]:
        codec.write(document, destination / (name + ".json"))
    summary.update(
        policy_decisions=len(policy_run.report.decisions),
        policy_sale_date=str(investment.report(policy_output).sale_date),
    )
    (destination / "summary.json").write_text(std_json.dumps(summary, indent=2))
    print(std_json.dumps(summary))
