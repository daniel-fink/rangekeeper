"""Naming changes preserve recorded mathematics, units and deterministic draws."""
from rangekeeper.model.distribution import Distribution

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from uuid import UUID, uuid4
import numpy as np
import pytest
from rangekeeper.model import Model, Metadata, Binding


from rangekeeper.duration import make_periods
from rangekeeper.scenarios import market, Market, replay
from rangekeeper.migration import upgrade_scenario_names

FIXTURE = Path(__file__).parent / "fixtures/scenarios/market-v1.json"
RENAMES = {
    "volatility": "cumulative_volatility",
    "autoregression": "autoregressive_returns",
    "pricing_factor": "space_market_price_factors",
    "true_value": "asset_true_value",
    "implied_cap_rate": "implied_reversion_cap_rates",
}


def root():
    return Model.create(metadata=Metadata(id=UUID(int=17), schema_version="0.5.0"))


def plan(**kwargs):
    return market.make_plan(
        id=UUID(int=18),
        seed=12345,
        periods=make_periods(date(2021, 1, 1), frequency="year", count=6),
        **kwargs
    )


def test_shared_distribution_survives_serialization_and_calculations():
    from rangekeeper._schema.records import Distribution as Generated

    record = Distribution.symmetric(kind="triangular", mean=2, residual=1, units="AUD")
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
    invalid = Distribution(kind="pert", lower=2, upper=1, units="AUD")
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
        [(1 + c.magnitude) * v.magnitude for c, v in zip(cycle, levels)]
    )


def test_upgrade_and_seeded_generation_preserve_original_paths():
    before = json.loads(FIXTURE.read_text())
    original = deepcopy(before)
    upgraded = upgrade_scenario_names(before, revision_id=UUID(int=999))
    assert before == original
    assert str(upgraded.metadata.previous) == before["metadata"]["id"]
    old_values = {
        v["id"]: v for f in before["system"]["formulations"] for v in f["values"]
    }
    for identity, value in old_values.items():
        after = upgraded.value(UUID(identity)).to_data()
        assert {k: v for k, v in after.items() if k != "key"} == {
            k: v for k, v in value.items() if k != "key"
        }
    replayed = replay(upgraded)
    assert replayed.model == upgraded
    old_record = before["provenance"]["scenarios"][0]
    assert [s.identifier for s in replayed.realization.streams] == [
        s["identifier"] for s in old_record["streams"]
    ]
    fresh = market.generate(
        root(),
        plan(
            parameters={
                "volatility_per_period": Distribution.uniform(lower=0.02, upper=0.05)
            }
        ),
        scenario_keys=["naming-reference"],
    )[0]
    for binding in old_record["outputs"]:
        assert (
            fresh.resolve_output(
                RENAMES.get(binding["name"], binding["name"])
            ).flow.to_data()
            == old_values[binding["value"]]["flow"]
        )
    assert (
        fresh.resolve_input("volatility_per_period").quantity
        == replayed.resolve_input("volatility_per_period").quantity
    )
    with pytest.raises(ValueError, match="new revision"):
        upgrade_scenario_names(before, revision_id=UUID(before["metadata"]["id"]))
    with pytest.raises(ValueError, match="v1"):
        upgrade_scenario_names(upgraded.to_data())
