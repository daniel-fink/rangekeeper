"""Finite Movement equations checked against an independent temporal oracle."""

from rangekeeper.model.expression import ValueReference
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


def test_forward_then_inverse_temporal_oracle():
    model, ids = oracle()
    store = MemoryStore()
    store.put(model)
    run = Executor(store).execute(investigate(model, ids))
    assert run.report.status.solution == "feasible", run.report.to_data()
    validate(run, resolver=store).raise_if_invalid()
    result = store.load_model(run.record.outputs[0])
    assert [
        m.magnitude for m in result.value(ids["cash"]).flow.movements
    ] == pytest.approx([100, 110, 121])
    assert result.value(ids["pv"]).quantity.magnitude == pytest.approx(3000 / 11)
    inverse = Executor(store).execute(investigate(result, ids, inverse=True))
    assert inverse.report.status.solution == "feasible", inverse.report.to_data()
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
    assert assign_flow(model, ids["cash"], keys=["y1"])[0].quantity.magnitude == 0
    with pytest.raises(ValueError, match="unresolved"):
        assign_flow(model, ids["cash"])
    for keys in (["absent"], ["y1", "y1"]):
        with pytest.raises(ValueError):
            unknown_flow(model, ids["cash"], keys=keys)
    specification = Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
            model=model.id,
            assignments=(
                Assignment(
                    target=movement(ids["cash"], "y1"),
                    quantity=Quantity(magnitude=25, units="AUD"),
                ),
            ),
            unknowns=(movement(ids["cash"], "y2"),),
        )
    )
    store = MemoryStore()
    store.put(model)
    run = Executor(store).execute(specification)
    assert run.report.status.solution == "feasible", run.report.to_data()
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
    from rangekeeper.model.flow import Period

    model, ids = oracle()
    builder = uuid4()
    first = growth.build_compound(
        model,
        id=builder,
        initial=scalar(ids["initial"]),
        rate=scalar(ids["rate"]),
        result=ids["cash"],
    )
    assert first == growth.build_compound(
        model,
        id=builder,
        initial=scalar(ids["initial"]),
        rate=scalar(ids["rate"]),
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
            key="inserted", period=Period(start=date(2026, 1, 1), end=date(2027, 1, 1))
        ).to_data(),
    )
    changed = model.revise(Update(system=System.from_data(data)))
    from rangekeeper.execution.symbols import key, units_for

    assert key(movement(ids["cash"], "y2")) == str(ids["cash"]) + "/y2"
    assert units_for(changed, movement(ids["cash"], "y2")) == "AUD"
    with pytest.raises(ValueError, match="coordinates"):
        flow.build_sum(
            changed, id=uuid4(), sources=[ids["cash"]], result=ids["discounted"]
        )


def test_movement_roles_conflicts_units_and_recorded_values_not_assignments():
    from rangekeeper.errors import ValidationError

    model, ids = oracle()
    store = MemoryStore()
    store.put(model)
    original = investigate(model, ids).to_data()
    # A resolved record is still not a role. An estimate is not a role either.
    original["unknowns"] = [
        r for r in original["unknowns"] if r.get("movement") != "y2"
    ]
    failed = Executor(store).execute(Specification.from_data(original))
    assert failed.report.status.solution == "not_assessed"
    for modify in ("duplicate", "overlap", "missing", "units"):
        data = investigate(model, ids).to_data()
        if modify == "duplicate":
            data["unknowns"].append(data["unknowns"][1])
        elif modify == "overlap":
            data["assignments"].append(
                dict(
                    target=movement(ids["cash"], "y1").to_data(),
                    quantity=dict(magnitude=1, units="AUD"),
                )
            )
        elif modify == "missing":
            data["unknowns"][1]["movement"] = "not-present"
        else:
            data["assignments"][0]["quantity"]["units"] = "m"
        try:
            spec = Specification.from_data(data)
        except ValidationError:
            assert modify in ("duplicate", "overlap")
        else:
            run = Executor(store).execute(spec)
            assert run.report.status.solution == "not_assessed"


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
            candidate[str(ids["cash"]) + "/y2"] += 1
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
    assert run.report.status.completion == "limited"
    assert any(d.code == "attempt_deadline" for d in run.report.diagnostics)


def test_explicit_draft_upgrade_preserves_order_and_requires_new_pins():
    import copy
    from rangekeeper.migration import upgrade_model, upgrade_specification

    model, ids = oracle()
    old = model.to_data()
    old["metadata"]["schema_version"] = "0.4.0"

    def unwrap(node):
        if isinstance(node, dict):
            if node.get("kind") == "reference":
                node["target"] = node["target"]["value"]
            for value in node.values():
                unwrap(value)
        elif isinstance(node, list):
            for value in node:
                unwrap(value)

    # A pre-Flow-expression document: remove equations rather than inventing an
    # old scalar encoding for references that never existed in that contract.
    old["system"]["formulations"] = []
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
    assert spec.record.assignments[0].target == scalar(ids["rate"])
    assert spec.record.unknowns == (scalar(ids["initial"]),)
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
                kind="flow",
                measure=model.value(ids["cash"]).measure,
                flow=Flow.from_data(template["flow"]),
            ).to_data()
        )
    model = model.revise(Update(system=System.from_data(data)))
    equations = [
        account.build_balance(
            model,
            id=uuid4(),
            movements=ids["cash"],
            initial=scalar(ids["initial"]),
            result=ids["discounted"],
        ),
        account.build_interest(
            model,
            id=uuid4(),
            principal=ids["discounted"],
            rate=scalar(ids["rate"]),
            result=ids["interest"],
            nonnegative_principal=True,
        ),
        flow.build_scale(
            model,
            id=uuid4(),
            source=ids["interest"],
            factor=scalar(ids["rate"]),
            result=ids["scaled"],
        ),
        flow.build_sum(
            model,
            id=uuid4(),
            sources=[ids["interest"], ids["scaled"]],
            result=ids["sum"],
        ),
        financial.build_reversion(
            model,
            id=uuid4(),
            income=ids["discounted"],
            capitalization=scalar(ids["rate"]),
            result=ids["reversion"],
            mapping={"y1": "y2", "y2": "y3", "y3": "y1"},
        ),
    ]
    data = model.system.to_data()
    data["formulations"] = [f.to_data() for f in equations]
    model = model.revise(Update(system=System.from_data(data)))
    assigned = [
        Assignment(
            target=scalar(ids["initial"]), quantity=Quantity(magnitude=100, units="AUD")
        ),
        Assignment(
            target=scalar(ids["rate"]), quantity=Quantity(magnitude=10, units="percent")
        ),
    ]
    assigned.extend(
        Assignment(
            target=movement(ids["cash"], f"y{i+1}"),
            quantity=Quantity(magnitude=x, units="AUD"),
        )
        for i, x in enumerate((10, -20, 5))
    )
    spec = Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
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
    assert run.report.status.solution == "feasible", run.report
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
        account.build_interest(
            model,
            id=uuid4(),
            principal=ids["discounted"],
            rate=scalar(ids["rate"]),
            result=ids["interest"],
            nonnegative_principal=False,
        )
