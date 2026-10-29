"""Executable Stream and acausal hierarchy examples for ADR-005 (no notebook state)."""

from datetime import date
from uuid import uuid4

from rangekeeper.duration import Frequency, Span
from rangekeeper.execution import execute
from rangekeeper.flow import Flow, ResampleMethod, Stream
from rangekeeper.io import MemoryStore
from rangekeeper.model import (
    Assembly,
    Characteristics,
    Definitions,
    Entity,
    Measure,
    Metadata,
    Model,
    System,
    Update,
    Value,
)
from rangekeeper.model.formulation import flow
from rangekeeper.model.system import FlowRollup, Hierarchy, View
from rangekeeper.schema.enums import SolutionStatus, ValueKind
from rangekeeper.specification import Specification, SpecificationRecord
from rangekeeper.specification.targets import assign_flow, unknown_flow


def collection():
    extent = Span(name="Operations", start=date(2027, 1, 1), length="11 years")
    monthly = extent.periods(frequency=Frequency.MONTH)
    stream = Stream(
        flows={
            "Rent": Flow.from_periods(monthly, [100.0] * len(monthly), units="AUD"),
            "Vacancy": Flow.from_periods(monthly, [-20.0] * len(monthly), units="AUD"),
        }
    )
    annual = stream.resample(
        periods=extent.periods(frequency=Frequency.YEAR), method=ResampleMethod.SUM
    )
    assert all(m.number == 960 for m in annual.sum().movements)
    return annual


def hierarchy_model():
    span = Span(name="Operations", start=date(2027, 1, 1), length="1 year")
    monthly, annual = (
        span.periods(frequency=Frequency.MONTH),
        span.periods(frequency=Frequency.YEAR),
    )
    money = Measure(id=uuid4(), code="money", name="Money", units="AUD")
    ids = {}
    entities = []

    def value(key, periods, amount):
        item = Value(
            id=uuid4(),
            key=key,
            kind=ValueKind.FLOW,
            measure=money.id,
            flow=Flow.from_periods(periods, [amount] * len(periods), units="AUD"),
        )
        return item

    for name, rent, expense in [("A", 100.0, -20.0), ("B", 200.0, -50.0)]:
        values = [
            value("rent", monthly, rent),
            value("expense", monthly, expense),
            value("net", monthly, None),
            value("annual", annual, None),
        ]
        ids.update({f"{name}_{v.key}": v.id for v in values})
        entity = Entity(
            id=uuid4(), name=name, characteristics=Characteristics(values=values)
        )
        entities.append(entity)
        ids[name] = entity.id
    total = value("portfolio", annual, None)
    ids["portfolio"] = total.id
    root = Assembly(
        id=uuid4(),
        name="Portfolio",
        entities=tuple(e.id for e in entities),
        characteristics=Characteristics(values=(total,)),
    )
    ids["root"] = root.id
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        definitions=Definitions(measures=(money,)),
        system=System(entities=entities, assemblies=(root,)),
    )
    equations = []
    for name in ("A", "B"):
        equations.append(
            flow.sum(
                model,
                id=uuid4(),
                summands=Stream.from_values(
                    model, [ids[f"{name}_rent"], ids[f"{name}_expense"]]
                ),
                total=ids[f"{name}_net"],
            )
        )
        equations.append(
            flow.resample(
                model,
                id=uuid4(),
                sequence=ids[f"{name}_net"],
                resampled=ids[f"{name}_annual"],
                method=ResampleMethod.SUM,
            )
        )
    hierarchy = Hierarchy(View(model), membership_root=root.id)
    equations.append(
        FlowRollup(key="annual").formulate(
            hierarchy, id=uuid4(), aggregates={root.id: total.id}
        )
    )
    model = model.revise(Update(system=model.system.replace(formulations=equations)))
    return model, ids


def forward_specification(model, ids):
    return Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
            model=model.id,
            assignments=tuple(
                a
                for name in ("A_rent", "A_expense", "B_rent", "B_expense")
                for a in assign_flow(model, ids[name])
            ),
            unknowns=tuple(
                r
                for name in ("A_net", "A_annual", "B_net", "B_annual", "portfolio")
                for r in unknown_flow(model, ids[name])
            ),
        ),
        model=model,
    )


def solve_example():
    from rangekeeper.quantity import Quantity

    model, ids = hierarchy_model()
    store = MemoryStore()
    store.put(model)
    forward = execute(forward_specification(model, ids), store).run
    assert forward.report.status.solution is SolutionStatus.FEASIBLE, (
        forward.report.to_data()
    )
    solved = store.load_model(forward.record.outputs[0])
    assert solved.value(ids["portfolio"]).flow.movements[0].number == 2760
    reverse = forward_specification(solved, ids).fix(
        {ids["portfolio"]: Quantity(magnitude=2880, units="AUD")}
    )
    reverse = reverse.free(solved.value(ids["A_rent"]).flow.movements[-1].id)
    inverse = execute(reverse, store).run
    assert inverse.report.status.solution is SolutionStatus.FEASIBLE, (
        inverse.report.to_data()
    )
    result = store.load_model(inverse.record.outputs[0])
    assert result.value(ids["A_rent"]).flow.movements[-1].number == 220
    assert result.value(ids["A_annual"]).flow.movements[0].number == 1080
    return result, ids


if __name__ == "__main__":
    print(collection().display())
    result, ids = solve_example()
    print(
        Stream.from_values(
            result,
            [ids["A_annual"], ids["B_annual"], ids["portfolio"]],
            names=["Building A", "Building B", "Portfolio"],
        ).display()
    )
