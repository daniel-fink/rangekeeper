"""Naming changes preserve recorded mathematics, units and deterministic draws."""

import json
from datetime import date
from pathlib import Path
from uuid import UUID

import numpy as np
import pytest

from rangekeeper.model import Binding, Metadata, Model
from rangekeeper.model.distribution import Distribution
from rangekeeper.model.duration import Frequency, make_periods
from rangekeeper.model.scenario import Market, market
from rangekeeper.schema.enums import DistributionFamily

FIXTURE = Path(__file__).parent / "fixtures/scenarios/market-v1.json"
RENAMES = {
    "volatility": "cumulative_volatility",
    "autoregression": "autoregressive_returns",
    "pricing_factor": "space_market_price_factors",
    "true_value": "asset_true_value",
    "implied_cap_rate": "implied_reversion_cap_rates",
}


def root():
    return Model.create(metadata=Metadata(id=UUID(int=17), schema_version="0.7.0"))


def plan(**kwargs):
    return market.make_plan(
        id=UUID(int=18),
        seed=12345,
        periods=make_periods(date(2021, 1, 1), frequency=Frequency.YEAR, count=6),
        **kwargs,
    )


def test_shared_distribution_survives_serialization_and_calculations():
    from rangekeeper.schema.records import Distribution as Generated

    record = Distribution.symmetric(
        kind=DistributionFamily.TRIANGULAR, mean=2, residual=1, units="AUD"
    )
    assert type(record) is Generated
    restored = Distribution.from_json(json.dumps(record.to_data()))
    assert restored == record
    assert sum(restored.mass([1, 2, 3])) == pytest.approx(1)
    assert record.sample(
        size=5, generator=np.random.default_rng(17)
    ) == restored.sample(size=5, generator=np.random.default_rng(17))
    data = record.to_data()
    data["lower"] = -99
    assert record.lower == 1
    with pytest.raises(AttributeError):
        record.lower = 0
    invalid = Distribution(kind=DistributionFamily.PERT, lower=2, upper=1, units="AUD")
    with pytest.raises(ValueError, match="bounds"):
        invalid.sample(size=1, generator=np.random.default_rng(1))


def test_component_authoring_preserves_plan_and_rejects_conflicts():
    grouped = plan(
        components=(
            market.make_trend(),
            market.make_volatility(),
            market.make_cyclicality(),
            market.make_noise(),
            market.make_black_swan(),
        )
    )
    assert grouped == plan()
    with pytest.raises(ValueError, match="duplicate component"):
        plan(
            components=(market.make_volatility(),),
            parameters={"volatility_per_period": 0.1},
        )
    with pytest.raises(ValueError, match="duplicate component"):
        plan(components=(market.make_trend(), market.make_trend()))


def test_market_view_is_revision_pinned_and_has_named_values():
    result = market.generate(root(), plan(), scenario_keys=["typed-market"])[0]
    assert type(result) is Market
    assert type(result.realization.inputs[0]) is Binding
    assert result.space_market_price_factors == result.resolve_output(
        "space_market_price_factors"
    )
    assert result.asset_true_value == result.model.value(result.asset_true_value.id)
    assert result.implied_reversion_cap_rates.flow.units == "dimensionless"
    assert result.cumulative_volatility != result.resolve_input("volatility_per_period")
    with pytest.raises(AttributeError):
        result.model = root()
    with pytest.raises(ValueError, match="belong"):
        Market(root(), result.realization)
    # Zero-centred variation remains distinct from the multiplicative waveform.
    levels = result.cumulative_volatility.flow.movements
    cycle = result.space_cycle.flow.movements
    rents = result.space_market.flow.movements
    assert [m.magnitude for m in rents] == pytest.approx(
        [(1 + c.magnitude) * v.magnitude for c, v in zip(cycle, levels, strict=True)]
    )
