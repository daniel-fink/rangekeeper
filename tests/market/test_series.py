"""Market dynamics and the paths that they generate (#299)."""

import math
from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.errors import ContractError, UnitError
from rangekeeper.market import Dynamics, PathGenerator, generate, generators
from rangekeeper.market._components import Draws, path
from rangekeeper.market._paths import construct_paths
from rangekeeper.market.contracts import DIRECT
from rangekeeper.market.series import GENERATOR, components
from rangekeeper.model import Distribution

YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)
RANDOM = Dynamics(
    trend="2 % pa",
    cycle_period="10 years",
    cycle_amplitude="10 %",
    volatility="5 % pa",
    noise="2 %",
    shock_probability="2 % pa",
    shock_size="-25 %",
)


def amounts(flow: rk.flow.Flow) -> list[float]:
    return [movement.number for movement in flow.movements]


def test_a_trend_is_fixed_and_takes_no_seed():
    paths = generate(
        dynamics={"rent_index": Dynamics(trend="2 % pa")}, periods=YEARS, count=1
    )
    (key,) = paths.keys
    index = paths[key]["rent_index"]
    assert index.units == "ratio"
    assert amounts(index) == pytest.approx([1.02**i for i in range(len(YEARS))])
    assert paths.capture.seed is None and not paths.capture.streams
    with pytest.raises(ContractError, match="fixed"):
        generate(
            dynamics={"rent_index": Dynamics(trend="2 % pa")},
            periods=YEARS,
            seed=1,
            count=1,
        )


def test_a_cycle_multiplies_the_trend():
    cycle = Dynamics(trend="2 % pa").replace(
        cycle_period="10 years", cycle_amplitude="10 %"
    )
    paths = generate(dynamics={"rent_index": cycle}, periods=YEARS, count=1)
    expected = [
        1.02**i * (1 + 0.1 * math.sin(2 * math.pi * i / 10)) for i in range(len(YEARS))
    ]
    assert amounts(paths[paths.keys[0]]["rent_index"]) == pytest.approx(expected)


def test_random_dynamics_need_a_seed_and_name_their_random_components():
    with pytest.raises(ContractError) as missing:
        generate(dynamics={"rent_index": RANDOM}, periods=YEARS, count=2)
    assert "rent_index: volatility, noise, shock" in str(missing.value)
    assert missing.value.values["random"] == {
        "rent_index": ["volatility", "noise", "shock"]
    }


def test_the_same_seed_gives_the_same_paths():
    paths = generate(dynamics={"rent_index": RANDOM}, periods=YEARS, seed=1, count=5)
    again = generate(dynamics={"rent_index": RANDOM}, periods=YEARS, seed=1, count=5)
    other = generate(dynamics={"rent_index": RANDOM}, periods=YEARS, seed=2, count=5)
    assert paths == again and paths.id == again.id
    assert paths != other
    assert paths.keys == ("path_1", "path_2", "path_3", "path_4", "path_5")
    first = paths["path_1"]["rent_index"]
    assert first != paths["path_2"]["rent_index"]
    assert paths.regenerate(seed=1) == paths
    assert paths.regenerate(seed=2) == other


def test_streams_do_not_depend_on_the_count_or_the_other_series():
    few = generate(dynamics={"rent_index": RANDOM}, periods=YEARS, seed=7, count=2)
    many = generate(
        dynamics={"rent_index": RANDOM, "cost_index": RANDOM},
        periods=YEARS,
        seed=7,
        count=12,
    )
    assert many.keys[0] == "path_01"
    assert few["path_1"]["rent_index"] == many["path_01"]["rent_index"]
    assert many["path_01"]["cost_index"] != many["path_01"]["rent_index"]


def test_the_capture_record_keeps_the_generator_and_its_parameters():
    paths = generate(dynamics={"rent_index": RANDOM}, periods=YEARS, seed=3, count=2)
    capture = paths.capture
    assert capture.generator == "dynamics"
    assert capture.fingerprint == generators.describe(GENERATOR).fingerprint
    assert (capture.seed, capture.count) == (3, 2)
    assert capture.algorithm == "numpy.SeedSequence/PCG64"
    assert [p.name for p in capture.parameters] == list(RANDOM.parameters)
    assert {p.series for p in capture.parameters} == {"rent_index"}
    assert [s.name for s in capture.streams] == [
        "rent_index.volatility",
        "rent_index.noise",
        "rent_index.shock",
    ]
    assert [v.name for v in capture.versions] == ["python", "numpy"]
    assert isinstance(GENERATOR, PathGenerator) and "dynamics" in generators


def test_dynamics_match_the_earlier_market_method_on_the_same_draws():
    """The private components against ``_paths.construct_paths`` on the same draws.

    #299 requires the results of today's dynamics on the same draws. The
    earlier method is the private ``market`` scenario method, which #140
    removes with the scenario plan.
    """
    count = 12
    innovations = tuple(0.03 * math.sin(3.1 * i) for i in range(count))
    noise = tuple(0.015 * math.cos(1.7 * i) for i in range(count))
    events = (0.9, 0.5, 0.01, 0.7, *([0.5] * (count - 4)))
    parameters = {
        name: rule.default for name, rule in DIRECT.items() if rule.default is not None
    }
    parameters.update(
        growth_rate=0.02,
        volatility_per_period=0.03,
        space_period=10.0,
        space_amplitude=0.1,
        space_phase=0.0,
        noise_lower=-0.02,
        noise_upper=0.02,
        shock_likelihood=0.02,
        shock_impact=-0.25,
        shock_dissipation=0.5,
    )
    earlier, _ = construct_paths(
        "market",
        parameters,
        {"innovations": innovations, "noise": noise, "events": events},
    )
    parts = components(
        {
            "trend": 0.02,
            "cycle_period": 10.0,
            "cycle_amplitude": 0.1,
            "volatility": 0.03,
            "noise": 0.02,
            "shock_probability": 0.02,
            "shock_size": -0.25,
        },
        step=1.0,
    )
    level = path(
        components=parts.__class__(
            trend=parts.trend, cycle=parts.cycle, volatility=parts.volatility
        ),
        count=count,
        draws=Draws(innovations=innovations),
    )
    assert level == pytest.approx(earlier["space_market_price_factors"], rel=1e-12)
    full = path(
        components=parts,
        count=count,
        draws=Draws(innovations=innovations, noise=noise, events=events),
    )
    factors = [
        h / t
        for h, t in zip(
            earlier["historical_value"], earlier["asset_true_value"], strict=True
        )
    ]
    assert [f / s for f, s in zip(full, level, strict=True)] == pytest.approx(
        factors, rel=1e-12
    )


def test_rates_per_year_convert_for_shorter_periods():
    months = rk.duration.Periods(
        start=date(2027, 1, 1), frequency=rk.duration.Frequency.MONTH, count=13
    )
    paths = generate(
        dynamics={"rent_index": Dynamics(trend="12 % pa")}, periods=months, count=1
    )
    values = amounts(paths[paths.keys[0]]["rent_index"])
    assert values[12] == pytest.approx(1.12, rel=1e-12)
    yearly = components({"trend": 0.12, "volatility": 0.1}, step=1 / 12)
    assert yearly.volatility is not None
    assert yearly.volatility.scale == pytest.approx(0.1 / math.sqrt(12))


def test_a_distributed_parameter_is_drawn_once_for_each_path():
    spread = Dynamics(trend=Distribution.uniform(lower=0, upper=0.04, units="pa"))
    assert spread.random == ("trend",)
    with pytest.raises(ContractError, match="rent_index: trend"):
        generate(dynamics={"rent_index": spread}, periods=YEARS, count=2)
    paths = generate(dynamics={"rent_index": spread}, periods=YEARS, seed=4, count=3)
    growths = {
        round(amounts(paths[key]["rent_index"])[1] - 1, 12) for key in paths.keys
    }
    assert len(growths) == 3 and all(0 <= g <= 0.04 for g in growths)
    assert paths.capture.parameters[0].distribution is not None
    assert [s.name for s in paths.capture.streams] == ["rent_index.parameter.trend"]
    assert paths.regenerate(seed=4) == paths


def test_dynamics_check_their_parameters():
    with pytest.raises(ContractError, match="give cycle_amplitude"):
        Dynamics(cycle_period="10 years")
    with pytest.raises(ContractError, match="give shock_probability"):
        Dynamics(shock_size="-25 %")
    with pytest.raises(ContractError):
        Dynamics(volatility="-1 % pa")
    with pytest.raises(ContractError):
        Dynamics(trend="-100 % pa")
    with pytest.raises(ContractError):
        Dynamics(shock_probability="120 % pa", shock_size="-25 %")
    with pytest.raises(UnitError):
        Dynamics(trend="2 AUD")
    with pytest.raises(UnitError):
        Dynamics(trend=0.02)  # a number is a ratio, not a rate per year
    with pytest.raises(TypeError):
        Dynamics(noise=[0.02])  # type: ignore[arg-type]
    assert Dynamics(noise=0.02).parameters["noise"] == rk.Quantity(
        magnitude=0.02, units="ratio"
    )


def test_dynamics_are_immutable_values():
    trend = Dynamics(trend="2 % pa")
    cycle = trend.replace(cycle_period="10 years", cycle_amplitude="10 %")
    assert trend == Dynamics(trend="2 % pa") and cycle != trend
    assert cycle.replace(trend="3 % pa").parameters["cycle_period"] == rk.Quantity(
        text="10 years"
    )
    assert "cycle_period='10 years'" in repr(cycle)
    with pytest.raises(AttributeError):
        trend.trend = "3 % pa"  # type: ignore[attr-defined]


def test_generate_checks_its_inputs():
    trend = {"rent_index": Dynamics(trend="2 % pa")}
    with pytest.raises(ContractError):
        generate(dynamics=trend, periods=YEARS, count=0)
    with pytest.raises(TypeError):
        generate(dynamics=trend, periods=YEARS, count=1.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        generate(dynamics={"rent_index": "2 % pa"}, periods=YEARS, count=1)  # type: ignore[dict-item]
    random = {"rent_index": RANDOM}
    with pytest.raises(ContractError):
        generate(dynamics=random, periods=YEARS, seed=-1, count=1)
    with pytest.raises(TypeError):
        generate(dynamics=random, periods=YEARS, seed="1", count=1)  # type: ignore[arg-type]
    partial = rk.duration.Span(start=date(2027, 1, 1), end=date(2028, 7, 1)).periods(
        frequency=rk.duration.Frequency.YEAR, include_partial=True
    )
    with pytest.raises(ContractError, match="one length"):
        generate(dynamics=trend, periods=partial, count=1)


def test_independent_series_compose_with_flow_arithmetic():
    paths = generate(
        dynamics={
            "market_index": RANDOM,
            "hotel_factor": Dynamics(trend="0 % pa", volatility="6 % pa"),
        },
        periods=YEARS,
        seed=1,
        count=2,
    )
    one = paths[paths.keys[0]]
    hotel = one["market_index"] * one["hotel_factor"]
    assert amounts(hotel) == pytest.approx(
        [
            m * h
            for m, h in zip(
                amounts(one["market_index"]), amounts(one["hotel_factor"]), strict=True
            )
        ]
    )
