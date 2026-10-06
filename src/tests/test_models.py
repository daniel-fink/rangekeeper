"""Complete migrated teaching consumers, with independent deterministic expectations."""

import datetime
import math
import pytest
from rangekeeper.calculations import series
from rangekeeper.io import MemoryStore
from rangekeeper.execution import Executor
from rangekeeper.run import validate
from rangekeeper.model import Model, Metadata
from rangekeeper.duration import make_periods
from rangekeeper.model.scenario import Distribution
from rangekeeper.scenarios import generate, make_plan
from uuid import uuid4
from tests.models import linear, deterministic, probabilistic, flexible


def execute(consumer, model, **requirements):
    store = MemoryStore()
    store.put(model)
    run = Executor(store).execute(consumer.specify(model, **requirements))
    assert run.report.status.solution == "feasible", run.report.to_data()
    validate(run, resolver=store).raise_if_invalid()
    output = store.load_model(run.record.outputs[0])
    return consumer.report(output), run


def test_linear_known_data_regression():
    params = dict(
        units="AUD",
        start_date=datetime.date(2020, 1, 1),
        num_periods=10,
        acquisition_price=1000,
        frequency="year",
        growth_rate=0.02,
        initial_pgi=100.0,
        vacancy_rate=0.05,
        opex_pgi_ratio=0.35,
        capex_pgi_ratio=0.1,
        cap_rate=0.05,
        discount_rate=0.07,
    )
    result = linear.Model(params)
    assert math.isclose(
        result.disposition.movements[-1].magnitude, 1218.99, rel_tol=0.01
    )
    assert result.pv_sums.total().magnitude == pytest.approx(1000)
    assert abs(result.irr.residual.magnitude) < 1e-7
    assert len(result.investment_cashflows.movements) == 11


@pytest.mark.parametrize(
    "initial,increment,terminal", [(100, 0, 1000), (110, 3, 1294.08), (90, -3, 705.92)]
)
def test_deterministic_horizon_comparison(initial, increment, terminal):
    model = deterministic.formulate(
        deterministic.author(dict(initial_pgi=initial, addl_pgi_per_period=increment))
    )
    result, _ = execute(deterministic, model)
    curve = deterministic.values(result.model)["horizon_pv"].flow
    assert curve.movements[-1].magnitude == pytest.approx(terminal, abs=0.01)
    assert result.pv.magnitude == pytest.approx(curve.movements[-1].magnitude)
    assert result.sale_date == datetime.date(2030, 12, 31)
    assert abs(result.irr.residual.magnitude) < 1e-6


def test_probabilistic_and_flexible_use_identical_captured_paths():
    base = Model.create(metadata=Metadata(id=uuid4(), schema_version="0.5.0"))
    plan = make_plan(
        periods=make_periods(datetime.date(2021, 1, 1), frequency="year", count=4),
        seed=17,
        method="independent.v2",
        parameters=dict(
            space_factor=Distribution(
                kind="uniform", lower=1.3, upper=1.4, units="dimensionless"
            ),
            asset_cap=0.05,
        ),
    )
    scenario = generate(base, plan, scenario_keys=["paired"])[0]
    model = probabilistic.formulate(
        probabilistic.author(dict(num_periods=3), scenario=scenario)
    )
    fixed, _ = execute(probabilistic, model)
    policy = flexible.build_stop_gain_resale_policy(
        model, minimum_holding_periods=2, threshold=1.2
    )
    chosen, run = execute(flexible, model, policy=policy)
    assert chosen.sale_date == datetime.date(2022, 12, 31)
    assert fixed.sale_date == datetime.date(2023, 12, 31)
    assert len(run.report.decisions) == 2
    for name in ("space_market_price_factors", "historical_value"):
        value = scenario.value(name)
        assert (
            fixed.model.value(value.id).flow
            == chosen.model.value(value.id).flow
            == value.flow
            or name == "space_market_price_factors"
        )
        # Assigned observations may gain evidence; their magnitudes and coordinates stay identical.
        assert [
            (m.key, m.date, m.magnitude)
            for m in fixed.model.value(value.id).flow.movements
        ] == [
            (m.key, m.date, m.magnitude)
            for m in chosen.model.value(value.id).flow.movements
        ]
    output = flexible.values(chosen.model)
    assert output["total"].flow.movements[-1].magnitude == 0
    assert output["operations"].flow.movements[1].magnitude > 0
    assert output["disposition"].flow.movements[1].magnitude > 0
