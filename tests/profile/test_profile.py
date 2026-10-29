"""Explicit growth origins, padding and mass allocation after API retirement."""

from datetime import date

import pytest

from rangekeeper import profile
from rangekeeper.duration import Frequency, Periods
from rangekeeper.flow import Flow
from rangekeeper.model import Distribution
from rangekeeper.profile import GrowthMethod, PaddingMode
from rangekeeper.quantity import Quantity


def test_origin_replaces_implicit_range_index_offset():
    assert profile.grow_values(
        0, count=12, method=GrowthMethod.LINEAR, rate=1, origin=12
    ) == tuple(range(12, 24))


def test_linear_recurring_and_compound_values():
    assert profile.grow_values(
        0, count=10, method=GrowthMethod.LINEAR, rate=1
    ) == tuple(range(10))
    assert profile.grow_values(0, count=10) == (0,) * 10
    assert profile.grow_values(1, count=10, method=GrowthMethod.COMPOUND, rate=0.1)[
        -1
    ] == pytest.approx(2.357947691)


def test_padding_is_explicit_and_preserves_projection_origin():
    values = profile.grow_values(1, count=12, method=GrowthMethod.COMPOUND, rate=0.05)
    padded = profile.pad(
        values, before=12, after=25, left=PaddingMode.UNITIZE, right=PaddingMode.EXTEND
    )
    assert len(padded) == 49 and padded[:12] == (1,) * 12
    assert padded[12:24] == values
    assert padded[-1] == pytest.approx(1.710339358)


def test_pert_allocation_preserves_mass_without_padding_observations():
    periods = Periods(start=date(2000, 1, 1), frequency=Frequency.MONTH, count=12)
    flow = Flow.from_profile(
        profile=profile.SCurve(distribution=Distribution.pert()),
        periods=periods,
        total=Quantity(magnitude=1, units="meter"),
    )
    assert flow.total().number == pytest.approx(1)
    assert tuple(m.period for m in flow.movements) == tuple(periods)
