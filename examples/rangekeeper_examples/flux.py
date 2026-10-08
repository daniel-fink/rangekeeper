"""Executable Stream and acausal hierarchy examples for ADR-005 (no notebook state)."""

from datetime import date
from uuid import uuid4
from rangekeeper.model import (
    Model,
    Metadata,
    Definitions,
    System,
    Entity,
    Assembly,
    Characteristics,
    Value,
    Measure,
    Update,
)
from rangekeeper.schema.enums import ValueKind, SolutionStatus
from rangekeeper.model.flux import Flow, Stream
from rangekeeper.model.duration import Span, Frequency
from rangekeeper.model.formulation import flow
from rangekeeper.model.system import Hierarchy, View, Reduction
from rangekeeper.calculations.series import ResamplingMethod
from rangekeeper.specification import Specification, SpecificationRecord
from rangekeeper.specification.targets import assign_flow, unknown_flow
from rangekeeper.io import MemoryStore
from rangekeeper.run.execution import Executor


def collection():
    extent = Span.from_duration(
        name="Operations", start=date(2027, 1, 1), frequency=Frequency.YEAR, count=11
    )
    monthly = extent.periods(Frequency.MONTH)
    stream = Stream(
        {
            "Rent": Flow.from_periods(monthly, [100.0] * len(monthly), units="AUD"),
            "Vacancy": Flow.from_periods(monthly, [-20.0] * len(monthly), units="AUD"),
        }
    )
    annual = stream.resample(
        extent.periods(Frequency.YEAR), method=ResamplingMethod.SUM
    )
    assert all(m.number == 960 for m in annual.sum().movements)
    return annual


def hierarchy_model():
    span = Span.from_duration(
        name="Operations", start=date(2027, 1, 1), frequency=Frequency.YEAR, count=1
    )
    monthly, annual = span.periods(Frequency.MONTH), span.periods(Frequency.YEAR)
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
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
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
                method=ResamplingMethod.SUM,
            )
        )
    hierarchy = Hierarchy(View(model), membership_root=root.id)
    equations.append(
        Reduction.flows(key="annual").formulate(
            hierarchy, id=uuid4(), aggregates={root.id: total.id}
        )
    )
    model = model.revise(Update(system=model.system.replace(formulations=equations)))
    return model, ids


def forward_specification(model, ids):
    return Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
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
        )
    )


def solve_example():
    from rangekeeper.model import Quantity

    model, ids = hierarchy_model()
    store = MemoryStore()
    store.put(model)
    forward = Executor(store).execute(forward_specification(model, ids))
    assert (
        forward.report.status.solution is SolutionStatus.FEASIBLE
    ), forward.report.to_data()
    solved = store.load_model(forward.record.outputs[0])
    assert solved.value(ids["portfolio"]).flow.movements[0].number == 2760
    reverse = forward_specification(solved, ids).lock(
        ids["portfolio"],
        Quantity(magnitude=2880, units="AUD"),
        id=uuid4(),
        model=solved,
    )
    reverse = reverse.unlock(
        ids["A_rent"],
        ids=(solved.value(ids["A_rent"]).flow.movements[-1].id,),
        id=uuid4(),
        model=solved,
    )
    inverse = Executor(store).execute(reverse)
    assert (
        inverse.report.status.solution is SolutionStatus.FEASIBLE
    ), inverse.report.to_data()
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
            labels=["Building A", "Building B", "Portfolio"],
        ).display()
    )
