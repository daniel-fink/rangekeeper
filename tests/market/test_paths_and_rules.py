"""Determinism, captured-input replay and finite rules information boundaries."""

from datetime import date
from uuid import uuid4

import pytest

from rangekeeper.duration import Frequency, Periods
from rangekeeper.errors import Code
from rangekeeper.execution.rule import RuleCapabilityError, evaluate, observe
from rangekeeper.flow import Flow, Movement
from rangekeeper.market import replay
from rangekeeper.market.generation import generate, make_plan
from rangekeeper.model import (
    Definitions,
    Distribution,
    Formulation,
    Measure,
    Metadata,
    Model,
    Reference,
    System,
    Update,
    Value,
    ValueKind,
)
from rangekeeper.schema.enums import DistributionFamily, Severity, SolutionStatus
from rangekeeper.specification.rule import ObservationBinding
from rangekeeper_examples.investment import build_stop_gain_resale_rules


def base():
    return Model.create(metadata=Metadata(id=uuid4(), schema_version="1.0.0"))


def test_parallel_streams_and_replay(monkeypatch):
    model = base()
    plan = make_plan(
        periods=Periods(start=date(2027, 1, 1), frequency=Frequency.YEAR, count=4),
        seed=23,
    )
    first = generate(model, plan, scenario_keys=("one", "two"))
    other = generate(model, plan, scenario_keys=("two", "one"), workers=2)
    assert [r.model.to_data() for r in first] == [
        r.model.to_data() for r in reversed(other)
    ]

    def forbidden(*args, **kwargs):
        raise AssertionError("replay drew randomness")

    monkeypatch.setattr("rangekeeper.market.generation.create_generator", forbidden)
    assert replay(first[0].model).model is first[0].model


def test_fixed_market_oracle_and_shock_applied_once():
    params = dict(
        initial_value=2.0,
        growth_rate=0.1,
        cap_rate=0.5,
        volatility_per_period=0.0,
        space_amplitude=0.0,
        asset_amplitude=0.0,
        noise_lower=0.0,
        noise_upper=0.0,
        shock_likelihood=1.0,
        shock_impact=-0.2,
        shock_dissipation=0.5,
    )
    plan = make_plan(
        periods=Periods(start=date(2027, 1, 1), frequency=Frequency.YEAR, count=3),
        seed=2,
        parameters=params,
    )
    result = generate(base(), plan, scenario_keys=["fixed"])[0]
    assert [
        m.number for m in result.value("space_market").flow.movements
    ] == pytest.approx([2, 2.2, 2.42])
    assert [
        m.number for m in result.value("historical_value").flow.movements
    ] == pytest.approx([3.2, 3.96, 4.598])
    assert [
        m.number for m in result.value("shock_effect").flow.movements
    ] == pytest.approx([-0.2, -0.1, -0.05])
    ref = Reference(
        target=result.value("implied_reversion_cap_rates").flow.movements[0].id
    )
    with pytest.raises(RuleCapabilityError, match="unavailable"):
        observe(
            model=result.model,
            at=date(2027, 12, 31),
            bindings=[
                ObservationBinding(
                    name="forward", target=ref, available_at=date(2027, 1, 1)
                )
            ],
        )
    assert observe(
        model=result.model,
        at=date(2028, 12, 31),
        bindings=[ObservationBinding(name="forward", target=ref)],
    ).quantities[0].quantity.number == pytest.approx(2.2 / 3.2)


def rule_model(factors):
    measure = Measure(id=uuid4(), code="factor", name="Factor", units="dimensionless")
    periods = Periods(
        start=date(2027, 1, 1), frequency=Frequency.YEAR, count=len(factors)
    )
    values = []
    for name in ("pricing", "holding", "sale"):
        values.append(
            Value(
                id=uuid4(),
                key=name,
                kind=ValueKind.FLOW,
                measure=measure.id,
                flow=Flow(
                    units="dimensionless",
                    movements=tuple(
                        Movement(
                            id=uuid4(),
                            key=f"p{i + 1}",
                            period=p,
                            magnitude=factors[i] if name == "pricing" else None,
                        )
                        for i, p in enumerate(periods)
                    ),
                ),
            )
        )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        definitions=Definitions(measures=(measure,)),
        system=System(formulations=(Formulation(id=uuid4(), values=tuple(values)),)),
    )
    return model, {v.key: v for v in values}


@pytest.mark.parametrize(
    "factors,minimum,sale",
    [
        ([1.2, 1.2, 1.2], 1, 3),
        ([2, 2, 2], 2, 2),
        ([1, 1.3, 2], 1, 2),
        ([1, 1, 1.3], 1, 3),
        ([1, 1, 1], 1, 3),
    ],
)
def test_resale_dates_strict_threshold_and_holding(factors, minimum, sale):
    model, v = rule_model(factors)
    rules = build_stop_gain_resale_rules(
        model,
        id=uuid4(),
        pricing_factor=v["pricing"].id,
        holding=v["holding"].id,
        sale=v["sale"].id,
        threshold=1.2,
        minimum_holding_periods=minimum,
    )
    result = evaluate(rules=rules, model=model)
    sales = [
        a.quantity.magnitude
        for a in result.assignments
        if a.target.target in {m.id for m in v["sale"].flow.movements}
    ]
    holding = [
        a.quantity.magnitude
        for a in result.assignments
        if a.target.target in {m.id for m in v["holding"].flow.movements}
    ]
    assert sales == [int(i + 1 == sale) for i in range(len(factors))]
    assert holding == [int(i < sale) for i in range(len(factors))]
    assert result.evidence[-1].at == date(2026 + sale, 12, 31)
    assert result.evidence[-1].terminated
    assert model.value(id=v["sale"].id).flow.movements[0].magnitude is None


def test_future_changes_cannot_change_earlier_decision_and_missing_is_not_zero():
    model, v = rule_model([1, 1.1, 1.4])
    rules = build_stop_gain_resale_rules(
        model,
        id=uuid4(),
        pricing_factor=v["pricing"].id,
        holding=v["holding"].id,
        sale=v["sale"].id,
        threshold=1.2,
    )
    before = evaluate(rules=rules, model=model)
    data = model.system.to_data()
    data["formulations"][0]["values"][0]["flow"]["movements"][-1]["magnitude"] = 99
    revised = model.revise(Update(system=System.from_data(data)))
    assert evaluate(rules=rules, model=revised).evidence[:2] == before.evidence[:2]
    data["formulations"][0]["values"][0]["flow"]["movements"][0]["magnitude"] = None
    with pytest.raises(RuleCapabilityError, match="unresolved"):
        evaluate(rules=rules, model=model.revise(Update(system=System.from_data(data))))


def test_independent_realizations_capture_distribution_draws():
    plan = make_plan(
        periods=Periods(start=date(2027, 1, 1), frequency=Frequency.YEAR, count=3),
        seed=9,
        method="market.independent",
        parameters=dict(
            space_factor=Distribution(
                kind=DistributionFamily.PERT,
                lower=0.5,
                upper=1.5,
                mode=1,
                units="dimensionless",
            ),
            asset_cap=0.05,
        ),
    )
    result = generate(base(), plan, scenario_keys=["independent"])[0]
    assert [
        m.number for m in result.value("space_market_price_factors").flow.movements
    ] == [m.number for m in result.value("space_factor").flow.movements]
    assert replay(result.model).model.id == result.model.id


def test_supplied_innovations_realize_without_randomness(monkeypatch):
    from rangekeeper.market.generation import capture, realize

    plan = make_plan(
        periods=Periods(start=date(2027, 1, 1), frequency=Frequency.YEAR, count=3),
        seed=123,
        parameters=dict(
            initial_value=2.0,
            growth_rate=0.1,
            cap_rate=0.5,
            autoregression=0.5,
            mean_reversion=0.2,
            space_amplitude=0.0,
            asset_amplitude=0.0,
            noise_lower=0.0,
            noise_upper=0.0,
            shock_likelihood=0.0,
        ),
    )
    inputs = {p.name: p.quantity for p in plan.parameters}
    inputs.update(
        innovations=[0.01, 0.02, -0.01], noise=[0, 0, 0], events=[0.9, 0.9, 0.9]
    )
    model = base()

    def forbidden(*args, **kwargs):
        raise AssertionError("known-input construction drew randomness")

    monkeypatch.setattr("rangekeeper.market.generation.create_generator", forbidden)
    draws = capture(model, plan, scenario_key="known", inputs=inputs)
    result = realize(model, plan, draws=draws)
    assert [
        m.number for m in result.resolve_output("autoregressive_returns").flow.movements
    ] == pytest.approx([0.01, 0.025, 0.0025])
    assert [
        m.number for m in result.value("historical_value").flow.movements
    ] == pytest.approx([4, 4.5, 4.94125])
    assert replay(result.model).model.id == result.model.id
    assert result.realization.generator == "supplied"
    inputs["noise"] = [float("inf"), 0, 0]
    with pytest.raises(ValueError):
        capture(model, plan, scenario_key="bad", inputs=inputs)


def test_rule_run_rejects_forged_information_timing_and_actions():
    from rangekeeper.execution import execute
    from rangekeeper.io import MemoryStore
    from rangekeeper.run import Run, validate
    from rangekeeper_examples import investment

    model = investment.formulate(investment.author(dict(num_periods=2)))
    rules = investment.build_stop_gain_resale_rules(model, minimum_holding_periods=1)
    store = MemoryStore()
    store.put(model)
    run = execute(specification=investment.specify(model, rules=rules), store=store).run
    assert run.report.status.solution is SolutionStatus.FEASIBLE
    for mutation in ("availability", "assignment", "rule", "termination"):
        data = run.to_data()
        data["metadata"]["id"] = str(uuid4())
        decision = data["report"]["rule_evidence"][0]
        if mutation == "availability":
            decision["observations"][0]["available_at"] = "2000-01-01"
        elif mutation == "assignment":
            decision["assignments"][0]["quantity"]["magnitude"] = 0
        elif mutation == "rule":
            decision["rule"] = str(rules.decisions[0].rules[0].id)
        else:
            decision["terminated"] = True
        candidate = Run.from_data(data)
        assert not validate(run=candidate, resolver=store).valid


def test_control_roles_conflict_across_contributors_and_endogenous_observation_fails():
    from rangekeeper.execution import execute
    from rangekeeper.io import MemoryStore
    from rangekeeper.shared.errors import ValidationError
    from rangekeeper.specification import Specification, SpecificationRecord
    from rangekeeper_examples import investment

    model = investment.formulate(investment.author(dict(num_periods=2)))
    rules = investment.build_stop_gain_resale_rules(model, minimum_holding_periods=1)
    spec = investment.specify(model, rules=rules)
    store = MemoryStore()
    store.put(model)
    store.put(spec)
    other = Specification(
        record=SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
            model=model.id,
            rules=rules,
        )
    )
    store.put(other)
    joined = Specification(
        record=SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
            includes=(spec.id, other.id),
        )
    )
    with pytest.raises(ValidationError):
        joined.compose(resolver=store)
    data = spec.to_data()
    data["unknowns"].append(rules.targets[0].to_data())
    with pytest.raises(ValidationError):
        Specification.from_data(data).compose(resolver=store)
    observed = rules.decisions[0].observations[0].target
    data = spec.to_data()
    data["metadata"]["id"] = str(uuid4())
    data["assignments"] = [
        a for a in data["assignments"] if a["target"] != observed.to_data()
    ]
    data["unknowns"].append(observed.to_data())
    run = execute(specification=Specification.from_data(data), store=store).run
    assert not run.record.outputs
    assert [d.code for d in run.report.diagnostics if d.severity == Severity.ERROR] == [
        Code.UNSUPPORTED_CAPABILITY
    ]
