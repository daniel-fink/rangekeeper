"""Complete teaching models, with independent deterministic expectations."""

import datetime
import math

import pytest

from rangekeeper import execution
from rangekeeper.duration import Frequency, Periods
from rangekeeper.flow import Flow
from rangekeeper.io import MemoryStore
from rangekeeper.market import Paths
from rangekeeper.run import validate
from rangekeeper.schema.enums import SolutionStatus
from tests.integration.models import deterministic, flexible, linear, probabilistic


def execute(consumer, model, **requirements):
    store = MemoryStore()
    store.put(model)
    run = execution.execute(
        specification=consumer.specify(model, **requirements), store=store
    ).run
    assert run.report.status.solution is SolutionStatus.FEASIBLE, run.report.to_data()
    validate(run=run, resolver=store).raise_if_invalid()
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
    assert result.pv_sums.total().number == pytest.approx(1000)
    assert abs(result.irr.residual.number) < 1e-7
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
    assert curve.movements[-1].number == pytest.approx(terminal, abs=0.01)
    assert result.pv.number == pytest.approx(curve.movements[-1].number)
    assert result.sale_date == datetime.date(2030, 12, 31)
    assert abs(result.irr.residual.number) < 1e-6


def test_probabilistic_and_flexible_use_identical_captured_paths():
    periods = Periods(
        start=datetime.date(2021, 1, 1), frequency=Frequency.YEAR, count=4
    )

    def series(*magnitudes):
        return Flow.from_periods(periods=periods, magnitudes=magnitudes, units="ratio")

    paths = Paths.from_flows(
        flows={
            "paired": {
                "space_market_price_factors": series(1.35, 1.32, 1.38, 1.31),
                "asset_market": series(0.05, 0.05, 0.05, 0.05),
            }
        }
    )
    path = paths["paired"]
    model = probabilistic.formulate(
        probabilistic.author(
            dict(num_periods=3),
            factors=path["space_market_price_factors"],
            cap_rates=path["asset_market"],
        )
    )
    fixed, _ = execute(probabilistic, model)
    rules = flexible.build_stop_gain_resale_rules(
        model, minimum_holding_periods=2, threshold=1.2
    )
    chosen, run = execute(flexible, model, rules=rules)
    assert chosen.sale_date == datetime.date(2022, 12, 31)
    assert fixed.sale_date == datetime.date(2023, 12, 31)
    assert len(run.report.decision_evidence) == 2
    for key, name in (
        ("space_market_price_factors", "space_market_price_factors"),
        ("reversion_cap_rates", "asset_market"),
    ):
        recorded = [m.number for m in path[name].movements]
        # Assigned observations may gain evidence; their magnitudes and coordinates stay identical.
        for result in (fixed, chosen):
            flow = probabilistic.values(result.model)[key].flow
            assert [m.number for m in flow.movements] == recorded
        assert [
            (m.key, m.date, m.magnitude)
            for m in probabilistic.values(fixed.model)[key].flow.movements
        ] == [
            (m.key, m.date, m.magnitude)
            for m in probabilistic.values(chosen.model)[key].flow.movements
        ]
    output = flexible.values(chosen.model)
    assert output["total"].flow.movements[-1].magnitude == 0
    assert output["operations"].flow.movements[1].magnitude > 0
    assert output["disposition"].flow.movements[1].magnitude > 0
