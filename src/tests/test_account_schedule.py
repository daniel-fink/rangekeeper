"""Passive account declarations and independent schedules through scalar execution."""

from datetime import date
from pathlib import Path
import json
from uuid import UUID, uuid4
import pytest

from rangekeeper.calculations.account import Balance, CurrentInterest, InterestTreatment
from rangekeeper.model.duration import Frequency, make_periods
from rangekeeper.model.formulation import account, declare, flow
from rangekeeper.model.expression import authoring as expression
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
from rangekeeper.model.flow import Flow
from rangekeeper.model.expression import Reference
from rangekeeper.schema.enums import ValueKind, Operator, SolutionStatus
from rangekeeper.specification import Specification, SpecificationRecord, Assignment
from rangekeeper.specification.targets import unknown_flow
from rangekeeper.io import MemoryStore


def u(number):
    return UUID(int=number)


def fixture(*, flow_rate=False, reverse_rate=False):
    periods = make_periods(date(2026, 1, 1), frequency=Frequency.MONTH, count=2)
    ids = {
        name: u(i)
        for i, name in enumerate(
            ("starting", "rate", "transactions", "closing", "interest"), 1
        )
    }
    values = [
        Value(
            id=ids["starting"],
            key="starting",
            kind=ValueKind.MEASUREMENT,
            measure=u(100),
        )
    ]
    values.append(
        Value(
            id=ids["rate"],
            key="rate",
            kind=ValueKind.FLOW if flow_rate else ValueKind.MEASUREMENT,
            measure=u(101),
            **(
                {
                    "flow": Flow.from_periods(
                        periods, [None, None], units="dimensionless", ids=[u(70), u(71)]
                    )
                }
                if flow_rate
                else {}
            ),
        )
    )
    for name, base in (("transactions", 20), ("closing", 30), ("interest", 40)):
        values.append(
            Value(
                id=ids[name],
                key=name,
                kind=ValueKind.FLOW,
                measure=u(100),
                flow=Flow.from_periods(
                    periods, [None, None], units="AUD", ids=[u(base), u(base + 1)]
                ),
            )
        )
    model = Model.create(
        metadata=Metadata(id=u(200), schema_version="0.7.0"),
        definitions=Definitions(
            measures=(
                Measure(id=u(100), code="money", name="Money", units="AUD"),
                Measure(id=u(101), code="ratio", name="Ratio", units="dimensionless"),
            )
        ),
        system=System(
            entities=(
                Entity(
                    id=u(201), characteristics=Characteristics(values=tuple(values))
                ),
            )
        ),
    )
    return model, ids


def build(model, ids, **kwargs):
    return account.schedule(
        model,
        id=u(300),
        transactions=ids["transactions"],
        starting=Reference(target=ids["starting"]),
        rate=Reference(target=ids["rate"]),
        closing=ids["closing"],
        interest=ids["interest"],
        nonnegative_principal=True,
        **kwargs,
    )


def test_schedule_is_passive_stable_and_has_explicit_rate_guards():
    model, ids = fixture()
    before = model.to_data()
    result = build(
        model,
        ids,
        current_interest=CurrentInterest.INCLUDED,
        treatment=InterestTreatment.FINANCED,
    )
    assert model.to_data() == before
    assert len(result.expressions) == 14
    assert [e.operator for e in result.expressions[:7]] == [
        Operator.EQUAL,
        Operator.EQUAL,
        Operator.GREATER_THAN_OR_EQUAL,
        Operator.GREATER_THAN_OR_EQUAL,
        Operator.GREATER_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.LESS_THAN,
    ]
    assert result == build(
        model,
        ids,
        current_interest=CurrentInterest.INCLUDED,
        treatment=InterestTreatment.FINANCED,
    )
    # All symbol occurrences are owned separately, while their target IDs stay intact.
    assert len({e.id for e in result.expressions}) == 14
    assert all(
        m.magnitude is None for m in model.value(ids["transactions"]).flow.movements
    )


def test_shared_authoring_normalizes_duplicate_keys_and_keeps_input_trees():
    symbol = expression.reference(Reference(target=u(1)))
    equation = expression.equal(
        symbol, expression.add(symbol, expression.literal(1, "AUD"))
    )
    before = equation.to_data()
    result = declare(
        id=u(400), name="fixture", equations=[(u(500), equation)], values=[u(1), u(1)]
    )
    assert len(result.bindings) == 1 and equation.to_data() == before
    expected = json.loads(
        (Path(__file__).parent / "fixtures/formulation_identity.json").read_text()
    )
    assert result.to_data() == expected
    assert (
        result.expressions[0].operands[0].id
        != result.expressions[0].operands[1].operands[0].id
    )
    with pytest.raises(ValueError, match="duplicate equation key"):
        declare(
            id=u(400),
            name="fixture",
            equations=[(u(500), equation), (str(u(500)), equation)],
            values=[],
        )
    extended = declare(
        id=u(400),
        name="fixture",
        equations=[("inserted", expression.equal(symbol, symbol)), (u(500), equation)],
        values=[u(1)],
    )
    assert result.expressions[0] == extended.expressions[1]


@pytest.mark.parametrize("balance", list(Balance))
def test_schedule_rejects_inclusion_without_financing(balance):
    model, ids = fixture()
    with pytest.raises(ValueError, match="requires financed"):
        build(model, ids, balance=balance, current_interest=CurrentInterest.INCLUDED)


def test_schedule_rejects_empty_and_distinct_result_roles():
    model, ids = fixture()
    with pytest.raises(ValueError, match="distinct"):
        build(model, {**ids, "interest": ids["closing"]})
    data = model.system.to_data()
    for v in data["entities"][0]["characteristics"]["values"]:
        if v.get("flow") is not None:
            v["flow"]["movements"] = []
    empty = model.revise(Update(system=System.from_data(data)))
    with pytest.raises(ValueError, match="at least one"):
        build(empty, ids)


@pytest.mark.parametrize(
    "balance,current,treatment,expected_interest,expected_closing",
    [
        (
            Balance.OPENING,
            CurrentInterest.EXCLUDED,
            InterestTreatment.SEPARATE,
            [10, 12],
            [120, 90],
        ),
        (
            Balance.CLOSING,
            CurrentInterest.EXCLUDED,
            InterestTreatment.SEPARATE,
            [12, 9],
            [120, 90],
        ),
        (
            Balance.OPENING,
            CurrentInterest.EXCLUDED,
            InterestTreatment.FINANCED,
            [10, 13],
            [130, 113],
        ),
        (
            Balance.CLOSING,
            CurrentInterest.EXCLUDED,
            InterestTreatment.FINANCED,
            [12, 10.2],
            [132, 112.2],
        ),
        (
            Balance.OPENING,
            CurrentInterest.INCLUDED,
            InterestTreatment.FINANCED,
            [100 / 9, 1180 / 81],
            [1180 / 9, 9370 / 81],
        ),
        (
            Balance.CLOSING,
            CurrentInterest.INCLUDED,
            InterestTreatment.FINANCED,
            [40 / 3, 310 / 27],
            [400 / 3, 3100 / 27],
        ),
    ],
)
def test_fixed_rate_execution_matches_independent_schedules(
    balance, current, treatment, expected_interest, expected_closing
):
    model, ids = fixture()
    formulation = build(
        model, ids, balance=balance, current_interest=current, treatment=treatment
    )
    model = model.revise(
        Update(system=model.system.replace(formulations=(formulation,)))
    )
    run, store = execute_schedule(model, ids)
    assert run.report.status.solution is SolutionStatus.FEASIBLE, run.report.to_data()
    result = store.load_model(run.record.outputs[0])
    assert [
        m.number for m in result.value(ids["interest"]).flow.movements
    ] == pytest.approx(expected_interest)
    assert [
        m.number for m in result.value(ids["closing"]).flow.movements
    ] == pytest.approx(expected_closing)


def test_flow_rates_match_coordinates_without_reordering_the_schedule():
    model, ids = fixture(flow_rate=True)
    data = model.system.to_data()
    for value in data["entities"][0]["characteristics"]["values"]:
        if value.get("flow") is None:
            continue
        for movement, key in zip(value["flow"]["movements"], ("z", "a")):
            movement.pop("period")
            movement["date"] = "2026-01-01"
            movement["key"] = key
        if value["id"] == str(ids["rate"]):
            value["flow"]["movements"].reverse()
    model = model.revise(Update(system=System.from_data(data)))
    result = account.schedule(
        model,
        id=u(300),
        transactions=ids["transactions"],
        starting=Reference(target=ids["starting"]),
        rate=ids["rate"],
        closing=ids["closing"],
        interest=ids["interest"],
        nonnegative_principal=True,
    )
    interest_equations = result.expressions[::6]
    assert [
        equation.operands[1].operands[0].target.target
        for equation in interest_equations
    ] == [u(70), u(71)]
    # A recurrence result has its own stricter order contract.
    data = model.system.to_data()
    for value in data["entities"][0]["characteristics"]["values"]:
        if value["id"] == str(ids["closing"]):
            value["flow"]["movements"].reverse()
    changed = model.revise(Update(system=System.from_data(data)))
    with pytest.raises(ValueError, match="order"):
        account.schedule(
            changed,
            id=u(300),
            transactions=ids["transactions"],
            starting=Reference(target=ids["starting"]),
            rate=ids["rate"],
            closing=ids["closing"],
            interest=ids["interest"],
            nonnegative_principal=True,
        )


def execute_schedule(
    model, ids, *, starting=100, rate=10, fixed_rate=True, transaction_amounts=(20, -30)
):
    from rangekeeper.run.execution import Executor

    assignments = [
        Assignment(
            target=Reference(target=ids["starting"]),
            quantity=Quantity(magnitude=starting, units="AUD"),
        ),
        Assignment(
            target=Reference(target=ids["rate"]),
            quantity=Quantity(magnitude=rate, units="percent"),
        ),
    ]
    assignments.extend(
        Assignment(
            target=Reference(target=m.id),
            quantity=Quantity(magnitude=value, units="AUD"),
        )
        for m, value in zip(
            model.value(ids["transactions"]).flow.movements, transaction_amounts
        )
    )
    unknowns = (
        *unknown_flow(model, ids["closing"]),
        *unknown_flow(model, ids["interest"]),
    )
    if not fixed_rate:
        assignments = [a for a in assignments if a.target.target != ids["rate"]]
        unknowns += (Reference(target=ids["rate"]),)
    spec = Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
            model=model.id,
            assignments=tuple(assignments),
            unknowns=unknowns,
        )
    )
    store = MemoryStore()
    store.put(model)
    run = Executor(store).execute(spec)
    return run, store


@pytest.mark.parametrize("rate", [-100, 100, 110])
def test_false_fixed_strict_rate_predicates_cannot_publish(rate):
    model, ids = fixture()
    formulation = build(
        model,
        ids,
        current_interest=CurrentInterest.INCLUDED,
        treatment=InterestTreatment.FINANCED,
    )
    model = model.revise(
        Update(system=model.system.replace(formulations=(formulation,)))
    )
    run, _ = execute_schedule(model, ids, rate=rate)
    assert run.report.status.solution is not SolutionStatus.FEASIBLE
    assert not run.record.outputs


def test_unknown_rate_is_unsupported_even_with_zero_principal():
    model, ids = fixture()
    formulation = build(model, ids)
    model = model.revise(
        Update(system=model.system.replace(formulations=(formulation,)))
    )
    run, _ = execute_schedule(
        model, ids, starting=0, fixed_rate=False, transaction_amounts=(0, 0)
    )
    assert run.report.status.solution is SolutionStatus.NOT_ASSESSED
    assert not run.record.outputs


def test_symbolic_schedule_does_not_clip_overdrafts():
    model, ids = fixture()
    formulation = build(model, ids)
    model = model.revise(
        Update(system=model.system.replace(formulations=(formulation,)))
    )
    run, _ = execute_schedule(model, ids, starting=0, transaction_amounts=(-10, 0))
    assert run.report.status.solution is not SolutionStatus.FEASIBLE
    assert not run.record.outputs


def test_specialized_and_resale_declarations_keep_baseline_identities():
    from rangekeeper.model.formulation import growth
    from rangekeeper_examples.investment import build_stop_gain_resale_policy

    model, ids = fixture()
    expected = json.loads(
        (Path(__file__).parent / "fixtures/legacy_declarations.json").read_text()
    )
    # This fixture was recovered from the preserved pre-implementation runtime.
    # Policy field renaming changes layout; declaration and occurrence IDs stay fixed.
    expected["resale"]["decisions"] = expected["resale"].pop("points")
    actual = {
        "interest": account.interest(
            model,
            id=u(301),
            principal=ids["transactions"],
            rate=Reference(target=ids["rate"]),
            result=ids["interest"],
            nonnegative_principal=True,
        ),
        "accumulation": flow.accumulate(
            model,
            id=u(302),
            source=ids["transactions"],
            initial=Reference(target=ids["starting"]),
            result=ids["closing"],
        ),
        "compound": growth.compound(
            model,
            id=u(303),
            initial=Reference(target=ids["starting"]),
            rate=Reference(target=ids["rate"]),
            result=ids["closing"],
        ),
        "resale": build_stop_gain_resale_policy(
            model,
            id=u(304),
            pricing_factor=ids["transactions"],
            holding=ids["closing"],
            sale=ids["interest"],
            threshold=1.2,
            minimum_holding_periods=1,
        ),
    }
    assert {name: record.to_data() for name, record in actual.items()} == expected


def test_new_schedule_has_its_own_frozen_identity_contract():
    import hashlib

    model, ids = fixture()
    result = build(
        model,
        ids,
        current_interest=CurrentInterest.INCLUDED,
        treatment=InterestTreatment.FINANCED,
    )
    expected = json.loads(
        (Path(__file__).parent / "fixtures/account_schedule_identity.json").read_text()
    )
    assert [str(expression.id) for expression in result.expressions] == expected[
        "expressions"
    ]
    assert [str(constraint.id) for constraint in result.constraints] == expected[
        "constraints"
    ]
    assert (
        hashlib.sha256(
            json.dumps(
                result.to_data(), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        == expected["wire_sha256"]
    )
