"""Volatility can be made reproducible: an optional numpy Generator (or a seed for from_trends)."""
import datetime

import numpy as np
import pytest

import rangekeeper as rk


@pytest.fixture
def sequence():
    return rk.duration.Sequence.from_bounds(
        include_start=datetime.date(2026, 1, 1),
        frequency=rk.duration.Type.YEAR,
        bound=8)


@pytest.fixture
def trend(sequence):
    return rk.dynamics.trend.Trend(
        sequence=sequence,
        growth_rate=0.01,
        cap_rate=0.05,
        initial_value=1.0)


def build(trend, sequence, generator=None):
    return rk.dynamics.volatility.Volatility(
        trend=trend,
        volatility_per_period=0.10,
        autoregression_param=0.0,
        mean_reversion_param=0.0,
        sequence=sequence,
        generator=generator)


def test_without_a_generator_each_call_differs(trend, sequence):
    """The default behaviour is unchanged: unseeded draws."""
    first = build(trend, sequence).movements.to_numpy(dtype=float)
    second = build(trend, sequence).movements.to_numpy(dtype=float)
    assert not np.array_equal(first, second)


def test_the_same_seeded_generator_gives_the_same_volatility(trend, sequence):
    first = build(trend, sequence, np.random.default_rng(42)).movements.to_numpy(dtype=float)
    second = build(trend, sequence, np.random.default_rng(42)).movements.to_numpy(dtype=float)
    assert np.array_equal(first, second)


def test_a_different_seed_gives_a_different_volatility(trend, sequence):
    first = build(trend, sequence, np.random.default_rng(42)).movements.to_numpy(dtype=float)
    second = build(trend, sequence, np.random.default_rng(43)).movements.to_numpy(dtype=float)
    assert not np.array_equal(first, second)


def test_a_generator_is_used_in_order_across_periods(trend, sequence):
    """One generator is consumed period by period, so a longer sequence extends a shorter one."""
    long_seq = rk.duration.Sequence.from_bounds(
        include_start=datetime.date(2026, 1, 1),
        frequency=rk.duration.Type.YEAR,
        bound=12)
    long_trend = rk.dynamics.trend.Trend(
        sequence=long_seq, growth_rate=0.01, cap_rate=0.05, initial_value=1.0)
    short = build(trend, sequence, np.random.default_rng(7)).volatility.movements.to_numpy(dtype=float)
    long = build(long_trend, long_seq, np.random.default_rng(7)).volatility.movements.to_numpy(dtype=float)
    assert np.array_equal(short, long[:len(short)])


def test_from_trends_with_a_seed_is_reproducible_and_independent(trend, sequence):
    def run():
        return rk.dynamics.volatility.Volatility.from_trends(
            trends=[trend, trend, trend],
            volatility_per_period=0.10,
            autoregression_param=0.0,
            mean_reversion_param=0.0,
            sequence=sequence,
            seed=123)

    first = [v.movements.to_numpy(dtype=float) for v in run()]
    second = [v.movements.to_numpy(dtype=float) for v in run()]
    for a, b in zip(first, second):
        assert np.array_equal(a, b)
    # the same trend in three slots must not give three copies of one stream
    assert not np.array_equal(first[0], first[1])
    assert not np.array_equal(first[1], first[2])
