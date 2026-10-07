"""Finite Movement equations checked against an independent temporal oracle."""

from rangekeeper.duration import Frequency, PeriodTiming, DayCount
from rangekeeper.model.flow import MissingValueHandling
from rangekeeper.calculations.series import (
    AlignmentJoin,
    AggregationReducer,
    ResamplingReduction,
    MeanWeighting,
)
from rangekeeper.calculations.projection import ProjectionMethod
from rangekeeper.account import Balance, CurrentInterest, InterestTreatment
from rangekeeper._schema.enums import ValueKind, SolutionStatus, CompletionStatus

from rangekeeper.model.expression import Reference
from dataclasses import replace
from datetime import date
from uuid import uuid4
import pytest

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
    assign_flow,
    unknown_flow,
)
from rangekeeper.execution import Executor
from rangekeeper.io import MemoryStore
from rangekeeper.run import validate


def oracle():
    ids = {name: uuid4() for name in ("initial", "rate", "cash", "discounted", "pv")}
    money, ratio = uuid4(), uuid4()
    periods = make_periods(date(2027, 1, 1), frequency=Frequency.YEAR, count=3)
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
                        Movement(id=uuid4(), key=f"y{i+1}", period=p)
                        for i, p in enumerate(periods)
                    ),
                ),
            )
        )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
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
            model,
            id=uuid4(),
            initial=Reference(target=ids["initial"]),
            rate=Reference(target=ids["rate"]),
            result=ids["cash"],
        ),
        financial.discount(
            model,
            id=uuid4(),
            source=ids["cash"],
            rate=Reference(target=ids["rate"]),
            result=ids["discounted"],
        ),
        financial.present_value(
            model,
            id=uuid4(),
            source=ids["discounted"],
            result=Reference(target=ids["pv"]),
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
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
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
        )
    )


def test_forward_then_inverse_temporal_oracle():
    model, ids = oracle()
    store = MemoryStore()
    store.put(model)
    run = Executor(store).execute(investigate(model, ids))
    assert run.report.status.solution == SolutionStatus.FEASIBLE, run.report.to_data()
    validate(run, resolver=store).raise_if_invalid()
    result = store.load_model(run.record.outputs[0])
    assert [
        m.magnitude for m in result.value(ids["cash"]).flow.movements
    ] == pytest.approx([100, 110, 121])
    assert result.value(ids["pv"]).quantity.magnitude == pytest.approx(3000 / 11)
    inverse = Executor(store).execute(investigate(result, ids, inverse=True))
    assert (
        inverse.report.status.solution == SolutionStatus.FEASIBLE
    ), inverse.report.to_data()
    output = store.load_model(inverse.record.outputs[0])
    assert output.value(ids["initial"]).quantity.magnitude == pytest.approx(110)
    assert output.metadata.previous == result.id
    assert all(m.magnitude is None for m in model.value(ids["cash"]).flow.movements)


def test_explicit_flow_roles_preserve_missing_null_zero_and_unrelated_entries():
    from rangekeeper._schema.records import Formulation
    from rangekeeper.errors import ValidationError

    model, ids = oracle()
    data = model.system.to_data()
    data["formulations"] = []
    cash = next(
        v
        for v in data["entities"][0]["characteristics"]["values"]
        if v["id"] == str(ids["cash"])
    )
    cash["flow"]["movements"][0]["magnitude"] = 0
    cash["flow"]["movements"][1]["magnitude"] = None
    cash["flow"]["movements"][2]["magnitude"] = 99
    model = model.revise(Update(system=System.from_data(data)))
    assert (
        assign_flow(
            model, ids["cash"], ids=[model.value(ids["cash"]).flow.movements[0].id]
        )[0].quantity.magnitude
        == 0
    )
    with pytest.raises(ValueError, match="unresolved"):
        assign_flow(model, ids["cash"])
    for selected in ([uuid4()], [model.value(ids["cash"]).flow.movements[0].id] * 2):
        with pytest.raises(ValueError):
            unknown_flow(model, ids["cash"], ids=selected)
    specification = Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
            model=model.id,
            assignments=(
                Assignment(
                    target=Reference(
                        target=next(
                            m.id
                            for m in model.value(ids["cash"]).flow.movements
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
                        for m in model.value(ids["cash"]).flow.movements
                        if m.key == "y2"
                    )
                ),
            ),
        )
    )
    store = MemoryStore()
    store.put(model)
    run = Executor(store).execute(specification)
    assert run.report.status.solution == SolutionStatus.FEASIBLE, run.report.to_data()
    result = store.load_model(run.record.outputs[0])
    movements = result.value(ids["cash"]).flow.movements
    assert [m.magnitude for m in movements] == [25, 0, 99]
    assert (
        movements[2].to_data() == model.value(ids["cash"]).flow.movements[2].to_data()
    )
    assert model.value(ids["cash"]).flow.movements[0].magnitude == 0
    detached = result.to_data()
    detached["system"]["entities"][0]["characteristics"]["values"][-2]["flow"][
        "movements"
    ][0]["magnitude"] = 1
    assert result.value(ids["cash"]).flow.movements[0].magnitude == 25
    with pytest.raises(AttributeError):
        movements[0].magnitude = 1


def test_stable_references_builder_ids_and_coordinate_mismatch():
    from rangekeeper.model.duration import Period

    model, ids = oracle()
    builder = uuid4()
    first = growth.compound(
        model,
        id=builder,
        initial=Reference(target=ids["initial"]),
        rate=Reference(target=ids["rate"]),
        result=ids["cash"],
    )
    assert first == growth.compound(
        model,
        id=builder,
        initial=Reference(target=ids["initial"]),
        rate=Reference(target=ids["rate"]),
        result=ids["cash"],
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
            period=Period(
                start_inclusive=date(2026, 1, 1), end_exclusive=date(2027, 1, 1)
            ),
        ).to_data(),
    )
    changed = model.revise(Update(system=System.from_data(data)))
    from rangekeeper.model.scope import target_units

    reference = Reference(
        target=next(
            m.id for m in model.value(ids["cash"]).flow.movements if m.key == "y2"
        )
    )
    assert reference.target == model.value(ids["cash"]).flow.movements[1].id
    assert (
        target_units(
            changed,
            Reference(
                target=next(
                    m.id
                    for m in model.value(ids["cash"]).flow.movements
                    if m.key == "y2"
                )
            ),
        )
        == "AUD"
    )
    with pytest.raises(ValueError, match="coordinates"):
        flow.sum(changed, id=uuid4(), sources=[ids["cash"]], result=ids["discounted"])


def test_movement_roles_conflicts_units_and_recorded_values_not_assignments():
    from rangekeeper.errors import ValidationError

    model, ids = oracle()
    store = MemoryStore()
    store.put(model)
    original = investigate(model, ids).to_data()
    # A resolved record is still not a role. An estimate is not a role either.
    original["unknowns"] = [
        r
        for r in original["unknowns"]
        if r["target"] != str(model.value(ids["cash"]).flow.movements[1].id)
    ]
    failed = Executor(store).execute(Specification.from_data(original))
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
                            for m in model.value(ids["cash"]).flow.movements
                            if m.key == "y1"
                        )
                    ).to_data(),
                    quantity=dict(magnitude=1, units="AUD"),
                )
            )
        elif modify == "missing":
            data["unknowns"][1]["target"] = str(uuid4())
        else:
            data["assignments"][0]["quantity"]["units"] = "m"
        try:
            spec = Specification.from_data(data)
        except ValidationError:
            assert modify in ("duplicate", "overlap")
        else:
            run = Executor(store).execute(spec)
            assert run.report.status.solution == SolutionStatus.NOT_ASSESSED


def test_movement_candidate_rejection_and_expansion_limits():
    from rangekeeper.execution.backends import PyomoHighs
    from rangekeeper._schema.records import Settings

    model, ids = oracle()
    store = MemoryStore()
    store.put(model)
    before = model.to_data()

    class WrongCandidate:
        def solve(self, *args, **kwargs):
            result = PyomoHighs().solve(*args, **kwargs)
            candidate = dict(result.candidate)
            candidate[model.value(ids["cash"]).flow.movements[1].id] += 1
            return replace(result, candidate=candidate)

    run = Executor(store, backend=WrongCandidate()).execute(investigate(model, ids))
    assert not run.record.outputs
    assert store.load_model(model.id).to_data() == before
    data = investigate(model, ids).to_data()
    data["settings"] = dict(symbol_limit=2, constraint_limit=2)
    run = Executor(store).execute(Specification.from_data(data))
    assert not run.record.outputs
    assert any("symbol limit" in d.message for d in run.report.diagnostics)


def test_preparation_deadline_and_constraint_limit_prevent_backend_call(monkeypatch):
    import time
    from rangekeeper.execution import preparation

    model, ids = oracle()
    store = MemoryStore()
    store.put(model)

    class ForbiddenBackend:
        def solve(self, *args, **kwargs):
            raise AssertionError("limited attempt invoked the backend")

    spec = investigate(model, ids).to_data()
    spec["settings"] = dict(constraint_limit=1)
    run = Executor(store, backend=ForbiddenBackend()).execute(
        Specification.from_data(spec)
    )
    assert not run.record.outputs
    assert any("constraint limit" in d.message for d in run.report.diagnostics)
    spec["metadata"]["id"] = str(uuid4())
    spec["settings"] = dict(time_limit=0.001)
    run = Executor(store, backend=ForbiddenBackend()).execute(
        Specification.from_data(spec)
    )
    assert run.report.status.completion == CompletionStatus.LIMITED
    assert any(d.code == "attempt_deadline" for d in run.report.diagnostics)


def test_explicit_draft_upgrade_preserves_order_and_requires_new_pins():
    import copy
    from rangekeeper.migration import upgrade_model, upgrade_specification

    model, ids = oracle()
    old = model.to_data()
    old["metadata"]["schema_version"] = "0.4.0"

    def unwrap(node):
        if isinstance(node, dict):
            if "start_inclusive" in node and "end_exclusive" in node:
                node["start"] = node.pop("start_inclusive")
                node["end"] = node.pop("end_exclusive")
            if node.get("kind") == "reference":
                node["target"] = node["target"]["target"]
            for value in node.values():
                unwrap(value)
        elif isinstance(node, list):
            for value in node:
                unwrap(value)

    # A pre-Flow-expression document: remove equations rather than inventing an
    # old scalar encoding for references that never existed in that contract.
    old["system"]["formulations"] = []
    unwrap(old)
    before = copy.deepcopy(old)
    upgraded = upgrade_model(old)
    assert old == before and upgraded.metadata.previous == model.id
    assert upgraded.value(ids["cash"]).flow == model.value(ids["cash"]).flow
    scalar_spec = dict(
        metadata=dict(id=str(uuid4()), schema_version="0.4.0"),
        model=old["metadata"]["id"],
        assignments=[
            dict(
                value=str(ids["rate"]),
                quantity=dict(magnitude=0.1, units="dimensionless"),
            )
        ],
        unknowns=[str(ids["initial"])],
    )
    with pytest.raises(ValueError, match="explicitly"):
        upgrade_specification(scalar_spec)
    spec = upgrade_specification(scalar_spec, model=upgraded.id)
    assert spec.record.assignments[0].target == Reference(target=ids["rate"])
    assert spec.record.unknowns == (Reference(target=ids["initial"]),)
    assert spec.record.model == upgraded.id
    assert (
        spec.metadata.previous == scalar_spec["metadata"]["id"]
        or str(spec.metadata.previous) == scalar_spec["metadata"]["id"]
    )
    with pytest.raises(ValueError, match="new revision"):
        upgrade_model(old, revision_id=model.id)


def test_finite_balance_interest_scaling_sum_and_explicit_reversion_mapping():
    """Use independently computed amounts to exercise the remaining builders."""
    from rangekeeper.formulations import account

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
                measure=model.value(ids["cash"]).measure,
                flow=Flow.from_data(template["flow"]).clone(),
            ).to_data()
        )
    model = model.revise(Update(system=System.from_data(data)))
    equations = [
        flow.accumulate(
            model,
            id=uuid4(),
            source=ids["cash"],
            initial=Reference(target=ids["initial"]),
            result=ids["discounted"],
        ),
        account.interest(
            model,
            id=uuid4(),
            principal=ids["discounted"],
            rate=Reference(target=ids["rate"]),
            result=ids["interest"],
            nonnegative_principal=True,
        ),
        flow.scale(
            model,
            id=uuid4(),
            source=ids["interest"],
            factor=Reference(target=ids["rate"]),
            result=ids["scaled"],
        ),
        flow.sum(
            model,
            id=uuid4(),
            sources=[ids["interest"], ids["scaled"]],
            result=ids["sum"],
        ),
        financial.reversion(
            model,
            id=uuid4(),
            income=ids["discounted"],
            capitalization=Reference(target=ids["rate"]),
            result=ids["reversion"],
            mapping={
                out.id: model.value(ids["discounted"]).flow.movements[(i + 1) % 3].id
                for i, out in enumerate(model.value(ids["reversion"]).flow.movements)
            },
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
                    for m in model.value(ids["cash"]).flow.movements
                    if m.key == f"y{i+1}"
                )
            ),
            quantity=Quantity(magnitude=x, units="AUD"),
        )
        for i, x in enumerate((10, -20, 5))
    )
    spec = Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
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
    run = Executor(store).execute(spec)
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
            m.magnitude for m in output.value(ids[name]).flow.movements
        ] == pytest.approx(expected)
    with pytest.raises(ValueError, match="overdraft"):
        account.interest(
            model,
            id=uuid4(),
            principal=ids["discounted"],
            rate=Reference(target=ids["rate"]),
            result=ids["interest"],
            nonnegative_principal=False,
        )
