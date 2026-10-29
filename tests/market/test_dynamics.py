"""Known-input dynamics without constructor execution or implicit random state.

Full market realization, replay, paired financial models and declarative rules
behaviour are covered by test_paths_and_rules and the integration tests.
"""

import math

import numpy as np
import pytest

from rangekeeper.errors import ContractError, NumericalError
from rangekeeper.market.dynamics import (
    accumulate_volatility,
    calculate_autoregression,
    calculate_cycle,
    calculate_shock,
    calculate_trend,
)
from rangekeeper.model import Distribution, DistributionFamily


def test_trend_preserves_explicit_initial_value_and_default_price_factor():
    growth = -0.002537905
    values = calculate_trend(
        count=25, cap_rate=0.05, growth_rate=growth, initial_value=0.050747414
    )
    assert values == pytest.approx(
        tuple(0.050747414 * (1 + growth) ** i for i in range(25))
    )
    assert calculate_trend(count=1, cap_rate=0.05, growth_rate=0) == (0.05,)


def test_autoregression_from_fixed_innovations():
    assert calculate_autoregression(
        (0.1, -0.2, 0, 0.3), parameter=0.2
    ) == pytest.approx((0.1, -0.18, -0.036, 0.2928))


def test_noise_uses_caller_generator_without_global_state():
    spec = Distribution.symmetric(
        kind=DistributionFamily.TRIANGULAR, mean=0, residual=0.05
    )
    np.random.seed(29)
    before = np.random.get_state()
    left = spec.sample(size=25, generator=np.random.default_rng(13))
    right = spec.sample(size=25, generator=np.random.default_rng(13))
    assert left == right and len(left) == 25
    assert all(-0.05 <= x <= 0.05 for x in left)
    after = np.random.get_state()
    assert (
        before[0] == after[0]
        and np.array_equal(before[1], after[1])
        and before[2:] == after[2:]
    )


def test_shock_has_one_onset_and_dissipates_once():
    assert calculate_shock(
        (0.5, 0.04, 0.01, 0.03), likelihood=0.05, dissipation=0.3, impact=-0.25
    ) == pytest.approx((0, -0.25, -0.175, -0.1225))
    assert calculate_shock(
        (0.5, 0.8), likelihood=0.05, dissipation=0.3, impact=-0.25
    ) == (0, 0)


@pytest.mark.parametrize(
    "call",
    [
        lambda: calculate_cycle(count=-1, period=4, phase=0, amplitude=1),
        lambda: calculate_cycle(count=2, period=math.inf, phase=0, amplitude=1),
        lambda: calculate_autoregression([math.nan], parameter=0.5),
        lambda: accumulate_volatility(
            [1.0], [0.0, 0.1], growth_rate=0, mean_reversion=0
        ),
        lambda: calculate_shock([0.5], likelihood=2, dissipation=0.5),
        lambda: calculate_shock([1.5], likelihood=0.5, dissipation=0.5),
    ],
)
def test_kernel_values_raise_contract_errors(call):
    with pytest.raises(ContractError):
        call()


def test_kernel_count_type_and_overflow():
    with pytest.raises(TypeError, match="count"):
        calculate_cycle(count=2.0, period=4, phase=0, amplitude=1)
    with pytest.raises(NumericalError, match="overflowed"):
        accumulate_volatility(
            [1e308, 1e308], [0.0, 1e308], growth_rate=0, mean_reversion=0
        )
