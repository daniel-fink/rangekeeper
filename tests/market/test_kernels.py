"""The private market kernels over supplied draws (#299).

``rk.market.Dynamics`` composes these kernels; ``test_series`` tests it. These
tests pin each kernel on known inputs, where a failure is easier to read than
through a generated path.
"""

import math

import numpy as np
import pytest

from rangekeeper.errors import ContractError, NumericalError
from rangekeeper.market._kernels import (
    accumulate_volatility,
    autoregression,
    cycle,
    shock,
    trend,
)
from rangekeeper.model import Distribution, DistributionFamily


def test_trend_compounds_from_one():
    growth = -0.002537905
    assert trend(count=25, rate=growth) == tuple((1 + growth) ** i for i in range(25))
    assert trend(count=2, rate=0.5) == (1.0, 1.5)


def test_autoregression_from_fixed_innovations():
    assert autoregression(
        innovations=(0.1, -0.2, 0, 0.3), parameter=0.2
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
    assert shock(
        events=(0.5, 0.04, 0.01, 0.03), probability=0.05, dissipation=0.3, size=-0.25
    ) == pytest.approx((0, -0.25, -0.175, -0.1225))
    assert shock(events=(0.5, 0.8), probability=0.05, dissipation=0.3, size=-0.25) == (
        0,
        0,
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda: cycle(count=-1, period=4, phase=0, amplitude=1),
        lambda: cycle(count=2, period=math.inf, phase=0, amplitude=1),
        lambda: autoregression(innovations=[math.nan], parameter=0.5),
        lambda: accumulate_volatility(
            trend=[1.0], returns=[0.0, 0.1], growth=0, mean_reversion=0
        ),
        lambda: shock(events=[0.5], probability=2, dissipation=0.5, size=1),
        lambda: shock(events=[1.5], probability=0.5, dissipation=0.5, size=1),
    ],
)
def test_kernel_values_raise_contract_errors(call):
    with pytest.raises(ContractError):
        call()


def test_kernel_count_type_and_overflow():
    with pytest.raises(TypeError, match="count"):
        cycle(count=2.0, period=4, phase=0, amplitude=1)
    with pytest.raises(NumericalError, match="overflowed"):
        accumulate_volatility(
            trend=[1e308, 1e308], returns=[0.0, 1e308], growth=0, mean_reversion=0
        )


def test_kernels_on_fixed_inputs():
    """Moved from tests/finance/test_calculations.py: these kernels are market maths."""
    assert cycle(count=4, period=4, phase=0, amplitude=2) == pytest.approx(
        [0, 2, 0, -2]
    )
    assert autoregression(innovations=[1, 0, 0], parameter=0.5) == (1, 0.5, 0.25)
    assert accumulate_volatility(
        trend=[100, 110, 121], returns=[0, 0.1, 0], growth=0.1, mean_reversion=0.5
    ) == pytest.approx([100, 120, 127])
    assert shock(
        events=[0.8, 0.1, 0.05, 0.2], probability=0.2, dissipation=0.5, size=-0.4
    ) == (0, -0.4, -0.2, -0.1)
