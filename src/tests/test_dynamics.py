"""Known-input dynamics without constructor execution or implicit random state.

Full market realization, replay, paired financial models and declarative policy
behaviour are covered by test_scenarios_policies, test_models and test_market_naming.
"""

from rangekeeper.model.distribution import DistributionFamily

from rangekeeper.model.distribution import Distribution

import numpy as np
import pytest
from rangekeeper.calculations.dynamics import calculate_trend
from rangekeeper.calculations.dynamics import calculate_autoregression
from rangekeeper.calculations.dynamics import calculate_shock


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
