"""Finite Movement equations checked against an independent temporal oracle."""

from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest

from rangekeeper.duration import Frequency
from rangekeeper.duration.period import Periods
from rangekeeper.errors import (
    Code,
    ContractError,
    MissingReferenceError,
    UnsupportedError,
)
from rangekeeper.execution import ExecutionConfig, execute
from rangekeeper.flow import Flow, Movement
from rangekeeper.io import MemoryStore
from rangekeeper.model import (
    Characteristics,
    Definitions,
    Entity,
    Measure,
    Metadata,
    Model,
    Reference,
    System,
    Update,
    Value,
)
from rangekeeper.model.expression.authoring import divide, equal, reference
from rangekeeper.model.formulation import financial, flow, growth
from rangekeeper.model.formulation.authoring import declare
from rangekeeper.quantity import Quantity
from rangekeeper.run import validate
from rangekeeper.schema.enums import CompletionStatus, SolutionStatus, ValueKind
from rangekeeper.specification import Assignment, Specification, SpecificationRecord
from rangekeeper.specification.targets import assign_flow, unknown_flow


def oracle():
    ids = {name: uuid4() for name in ("initial", "rate", "cash", "discounted", "pv")}
    money, ratio = uuid4(), uuid4()
    periods = Periods(start=date(2027, 1, 1), frequency=Frequency.YEAR, count=3)
    values = [
        Value(id=ids[name], key=name, kind=ValueKind.MEASUREMENT, measure=measure)
        for name, measure in [("initial", money), ("rate", ratio), ("pv", money)]
    ]
    for name in ("cash", "discounted"):
        values.append(
            Value(
                id=ids[name],
                key=name,
                kind=ValueKind.FLOW,
                measure=money,
                flow=Flow(
                    units="AUD",
                    movements=tuple(
                        Movement(id=uuid4(), key=f"y{i + 1}", period=p)
                        for i, p in enumerate(periods)
                    ),
                ),
            )
        )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
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
        growth.compound(
            model=model,
            id=uuid4(),
            initial=Reference(target=ids["initial"]),
            rate=Reference(target=ids["rate"]),
            series=ids["cash"],
        ),
        financial.discount(
            model=model,
            id=uuid4(),
            series=ids["cash"],
            rate=Reference(target=ids["rate"]),
            discounted=ids["discounted"],
        ),
        financial.pv(
            model=model,
            id=uuid4(),
            sequence=ids["discounted"],
            value=Reference(target=ids["pv"]),
        ),
    )
    data = model.system.to_data()
    data["formulations"] = [f.to_data() for f in equations]
    return model.revise(Update(system=System.from_data(data))), ids


def investigate(model, ids, *, inverse=False):
    fixed = "pv" if inverse else "initial"
    unknown = "initial" if inverse else "pv"
    return Specification(
        record=SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
            model=model.id,
            assignments=(
                Assignment(
                    target=Reference(target=ids[fixed]),
                    quantity=Quantity(magnitude=300 if inverse else 100, units="AUD"),
                ),
                Assignment(
                    target=Reference(target=ids["rate"]),
                    quantity=Quantity(magnitude=0.1, units="dimensionless"),
                ),
            ),
            unknowns=(
                Reference(target=ids[unknown]),
                *unknown_flow(model, ids["cash"]),
                *unknown_flow(model, ids["discounted"]),
            ),
        ),
        model=model,
    )


def test_forward_then_inverse_temporal_oracle():
    model, ids = oracle()
    store = MemoryStore()
    store.put(model)
    run = execute(specification=investigate(model, ids), store=store).run
    assert run.report.status.solution == SolutionStatus.FEASIBLE, run.report.to_data()
    validate(run=run, resolver=store).raise_if_invalid()
    result = store.load_model(run.record.outputs[0])
    assert [
        m.magnitude for m in result.value(id=ids["cash"]).flow.movements
    ] == pytest.approx([100, 110, 121])
    assert result.value(id=ids["pv"]).quantity.number == pytest.approx(3000 / 11)
    inverse = execute(
        specification=investigate(result, ids, inverse=True), store=store
    ).run
    assert inverse.report.status.solution == SolutionStatus.FEASIBLE, (
        inverse.report.to_data()
    )
    output = store.load_model(inverse.record.outputs[0])
    assert output.value(id=ids["initial"]).quantity.number == pytest.approx(110)
    assert output.metadata.previous == result.id
    assert all(m.magnitude is None for m in model.value(id=ids["cash"]).flow.movements)


def test_explicit_flow_roles_preserve_missing_null_zero_and_unrelated_entries():

    model, ids = oracle()
    data = model.system.to_data()
    data["formulations"] = []
    cash = next(
        v
        for v in data["entities"][0]["characteristics"]["values"]
        if v["id"] == str(ids["cash"])
    )
    cash["flow"]["movements"][0]["magnitude"] = "0"
    cash["flow"]["movements"][1]["magnitude"] = None
    cash["flow"]["movements"][2]["magnitude"] = "99"
    model = model.revise(Update(system=System.from_data(data)))
    assert (
        assign_flow(
            model, ids["cash"], ids=[model.value(id=ids["cash"]).flow.movements[0].id]
        )[0].quantity.magnitude
        == 0
    )
    with pytest.raises(ContractError, match="recorded amount"):
        assign_flow(model, ids["cash"])
    with pytest.raises(MissingReferenceError) as missing:
        unknown_flow(model, ids["cash"], ids=[uuid4()])
    assert (missing.value.kind, missing.value.by) == ("Movement", "id")
    first = model.value(id=ids["cash"]).flow.movements[0].id
    with pytest.raises(ContractError) as repeated:
        unknown_flow(model, ids["cash"], ids=[first, first])
    assert repeated.value.code is Code.UNIQUE
    specification = Specification(
        record=SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
            model=model.id,
            assignments=(
                Assignment(
                    target=Reference(
                        target=next(
                            m.id
                            for m in model.value(id=ids["cash"]).flow.movements
                            if m.key == "y1"
                        )
                    ),
                    quantity=Quantity(magnitude=25, units="AUD"),
                ),
            ),
            unknowns=(
                Reference(
                    target=next(
                        m.id
                        for m in model.value(id=ids["cash"]).flow.movements
                        if m.key == "y2"
                    )
                ),
            ),
        )
    )
    store = MemoryStore()
    store.put(model)
    run = execute(specification=specification, store=store).run
    assert run.report.status.solution == SolutionStatus.FEASIBLE, run.report.to_data()
    result = store.load_model(run.record.outputs[0])
    movements = result.value(id=ids["cash"]).flow.movements
    assert [m.magnitude for m in movements] == [25, 0, 99]
    assert (
        movements[2].to_data()
        == model.value(id=ids["cash"]).flow.movements[2].to_data()
    )
    assert model.value(id=ids["cash"]).flow.movements[0].magnitude == 0
    detached = result.to_data()
    detached["system"]["entities"][0]["characteristics"]["values"][-2]["flow"][
        "movements"
    ][0]["magnitude"] = 1
    assert result.value(id=ids["cash"]).flow.movements[0].magnitude == 25
    with pytest.raises(AttributeError):
        movements[0].magnitude = 1


def test_stable_references_builder_ids_and_coordinate_mismatch():
    from rangekeeper.duration import Period

    model, ids = oracle()
    builder = uuid4()
    first = growth.compound(
        model=model,
        id=builder,
        initial=Reference(target=ids["initial"]),
        rate=Reference(target=ids["rate"]),
        series=ids["cash"],
    )
    assert first == growth.compound(
        model=model,
        id=builder,
        initial=Reference(target=ids["initial"]),
        rate=Reference(target=ids["rate"]),
        series=ids["cash"],
    )
    data = model.system.to_data()
    cash = next(
        v
        for v in data["entities"][0]["characteristics"]["values"]
        if v["id"] == str(ids["cash"])
    )
    cash["flow"]["movements"].insert(
        0,
        Movement(
            id=uuid4(),
            key="inserted",
            period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1)),
        ).to_data(),
    )
    changed = model.revise(Update(system=System.from_data(data)))
    from rangekeeper.model.targets import target_units

    reference = Reference(
        target=next(
            m.id for m in model.value(id=ids["cash"]).flow.movements if m.key == "y2"
        )
    )
    assert reference.target == model.value(id=ids["cash"]).flow.movements[1].id
    assert (
        target_units(
            changed,
            Reference(
                target=next(
                    m.id
                    for m in model.value(id=ids["cash"]).flow.movements
                    if m.key == "y2"
                )
            ),
        )
        == "AUD"
    )
    with pytest.raises(ValueError, match="coordinates"):
        flow.sum(
            model=changed, id=uuid4(), summands=[ids["cash"]], total=ids["discounted"]
        )


def test_movement_roles_conflicts_units_and_recorded_values_not_assignments():
    from rangekeeper.shared.errors import ValidationError

    model, ids = oracle()
    store = MemoryStore()
    store.put(model)
    original = investigate(model, ids).to_data()
    # A resolved record is still not a role. An estimate is not a role either.
    original["unknowns"] = [
        r
        for r in original["unknowns"]
        if r["target"] != str(model.value(id=ids["cash"]).flow.movements[1].id)
    ]
    failed = execute(specification=Specification.from_data(original), store=store).run
    assert failed.report.status.solution == SolutionStatus.NOT_ASSESSED
    for modify in ("duplicate", "overlap", "missing", "units"):
        data = investigate(model, ids).to_data()
        if modify == "duplicate":
            data["unknowns"].append(data["unknowns"][1])
        elif modify == "overlap":
            data["assignments"].append(
                dict(
                    target=Reference(
                        target=next(
                            m.id
                            for m in model.value(id=ids["cash"]).flow.movements
                            if m.key == "y1"
                        )
                    ).to_data(),
                    quantity=dict(magnitude="1", units="AUD"),
                )
            )
        elif modify == "missing":
            data["unknowns"][1]["target"] = str(uuid4())
        else:
            data["assignments"][0]["quantity"] = dict(magnitude=100, units="m")
        try:
            spec = Specification.from_data(data)
        except ValidationError:
            assert modify in ("duplicate", "overlap")
        else:
            run = execute(specification=spec, store=store).run
            assert run.report.status.solution == SolutionStatus.NOT_ASSESSED


def test_movement_candidate_rejection_and_expansion_limits():
    from rangekeeper.execution.backends import PyomoHighs

    model, ids = oracle()
    store = MemoryStore()
    store.put(model)
    before = model.to_data()

    class WrongCandidate:
        def solve(self, *args, **kwargs):
            result = PyomoHighs().solve(*args, **kwargs)
            candidate = dict(result.candidate)
            candidate[model.value(id=ids["cash"]).flow.movements[1].id] += 1
            return replace(result, candidate=candidate)

    run = execute(
        specification=investigate(model, ids),
        store=store,
        config=ExecutionConfig(backend=WrongCandidate()),
    ).run
    assert not run.record.outputs
    assert store.load_model(model.id).to_data() == before
    data = investigate(model, ids).to_data()
    data["settings"] = dict(symbol_limit=2, constraint_limit=2)
    run = execute(specification=Specification.from_data(data), store=store).run
    assert not run.record.outputs
    assert any(d.code == Code.SYMBOL_LIMIT for d in run.report.diagnostics)


def test_preparation_deadline_and_constraint_limit_prevent_backend_call(monkeypatch):

    model, ids = oracle()
    store = MemoryStore()
    store.put(model)

    class ForbiddenBackend:
        def solve(self, *args, **kwargs):
            raise AssertionError("limited attempt invoked the backend")

    spec = investigate(model, ids).to_data()
    spec["settings"] = dict(constraint_limit=1)
    run = execute(
        specification=Specification.from_data(spec),
        store=store,
        config=ExecutionConfig(backend=ForbiddenBackend()),
    ).run
    assert not run.record.outputs
    assert any(d.code == Code.CONSTRAINT_LIMIT for d in run.report.diagnostics)
    spec["metadata"]["id"] = str(uuid4())
    spec["settings"] = dict(time_limit=0.001)
    run = execute(
        specification=Specification.from_data(spec),
        store=store,
        config=ExecutionConfig(backend=ForbiddenBackend()),
    ).run
    assert run.report.status.completion == CompletionStatus.LIMITED
    assert any(d.code == "attempt_deadline" for d in run.report.diagnostics)


def test_finite_balance_interest_scaling_sum_and_explicit_reversion_mapping():
    """Use independently computed amounts to exercise the remaining builders."""
    from rangekeeper.model.formulation import financial

    model, ids = oracle()
    data = model.system.to_data()
    data["formulations"] = []
    owned = data["entities"][0]["characteristics"]["values"]
    template = next(v for v in owned if v["id"] == str(ids["cash"]))
    for name in ("interest", "scaled", "sum", "reversion"):
        ids[name] = uuid4()
        owned.append(
            Value(
                id=ids[name],
                key=name,
                kind=ValueKind.FLOW,
                measure=model.value(id=ids["cash"]).measure,
                flow=Flow.from_data(template["flow"]).clone(),
            ).to_data()
        )
    model = model.revise(Update(system=System.from_data(data)))
    equations = [
        flow.accumulate(
            model=model,
            id=uuid4(),
            increments=ids["cash"],
            initial=Reference(target=ids["initial"]),
            accumulation=ids["discounted"],
        ),
        financial.interest(
            model=model,
            id=uuid4(),
            principal=ids["discounted"],
            rate=Reference(target=ids["rate"]),
            interest=ids["interest"],
            nonnegative_principal=True,
        ),
        flow.scale(
            model=model,
            id=uuid4(),
            multiplicand=ids["interest"],
            multiplier=Reference(target=ids["rate"]),
            product=ids["scaled"],
        ),
        flow.sum(
            model=model,
            id=uuid4(),
            summands=[ids["interest"], ids["scaled"]],
            total=ids["sum"],
        ),
        # Explicit mapped capitalisation; this cyclic test mapping is deliberate,
        # not a financial timing default.
        declare(
            id=uuid4(),
            name="reversion",
            equations=[
                (
                    out.id,
                    equal(
                        reference(Reference(target=out.id)),
                        divide(
                            reference(
                                Reference(
                                    target=model.value(id=ids["discounted"])
                                    .flow.movements[(i + 1) % 3]
                                    .id
                                )
                            ),
                            reference(Reference(target=ids["rate"])),
                        ),
                    ),
                )
                for i, out in enumerate(model.value(id=ids["reversion"]).flow.movements)
            ],
            values=(ids["discounted"], ids["rate"], ids["reversion"]),
        ),
    ]
    data = model.system.to_data()
    data["formulations"] = [f.to_data() for f in equations]
    model = model.revise(Update(system=System.from_data(data)))
    assigned = [
        Assignment(
            target=Reference(target=ids["initial"]),
            quantity=Quantity(magnitude=100, units="AUD"),
        ),
        Assignment(
            target=Reference(target=ids["rate"]),
            quantity=Quantity(magnitude=10, units="percent"),
        ),
    ]
    assigned.extend(
        Assignment(
            target=Reference(
                target=next(
                    m.id
                    for m in model.value(id=ids["cash"]).flow.movements
                    if m.key == f"y{i + 1}"
                )
            ),
            quantity=Quantity(magnitude=x, units="AUD"),
        )
        for i, x in enumerate((10, -20, 5))
    )
    spec = Specification(
        record=SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
            model=model.id,
            assignments=tuple(assigned),
            unknowns=tuple(
                ref
                for name in ("discounted", "interest", "scaled", "sum", "reversion")
                for ref in unknown_flow(model, ids[name])
            ),
        )
    )
    store = MemoryStore()
    store.put(model)
    run = execute(specification=spec, store=store).run
    assert run.report.status.solution == SolutionStatus.FEASIBLE, run.report
    output = store.load_model(run.record.outputs[0])
    for name, expected in {
        "discounted": [110, 90, 95],
        "interest": [11, 9, 9.5],
        "scaled": [1.1, 0.9, 0.95],
        "sum": [12.1, 9.9, 10.45],
        "reversion": [900, 950, 1100],
    }.items():
        assert [
            m.number for m in output.value(id=ids[name]).flow.movements
        ] == pytest.approx(expected)
    with pytest.raises(UnsupportedError, match="overdraft"):
        financial.interest(
            model=model,
            id=uuid4(),
            principal=ids["discounted"],
            rate=Reference(target=ids["rate"]),
            interest=ids["interest"],
            nonnegative_principal=False,
        )
