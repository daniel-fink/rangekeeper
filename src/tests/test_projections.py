"""Explicit projection origins, padding and mass allocation after API retirement."""

from rangekeeper.model.duration import Frequency
from rangekeeper.calculations.projection import ProjectionMethod
from rangekeeper.calculations.projection import PaddingMode

from rangekeeper.model.distribution import Distribution

from datetime import date
import pytest
from rangekeeper.calculations import projection, series
from rangekeeper.model.duration import make_periods

from rangekeeper.model.measure import Quantity


def test_origin_replaces_implicit_range_index_offset():
    assert projection.project_values(
        0, count=12, method=ProjectionMethod.LINEAR, rate=1, origin=12
    ) == tuple(range(12, 24))


def test_linear_recurring_and_compound_values():
    assert projection.project_values(
        0, count=10, method=ProjectionMethod.LINEAR, rate=1
    ) == tuple(range(10))
    assert projection.project_values(0, count=10) == (0,) * 10
    assert projection.project_values(
        1, count=10, method=ProjectionMethod.COMPOUND, rate=0.1
    )[-1] == pytest.approx(2.357947691)


def test_padding_is_explicit_and_preserves_projection_origin():
    values = projection.project_values(
        1, count=12, method=ProjectionMethod.COMPOUND, rate=0.05
    )
    padded = projection.pad(
        values, before=12, after=25, left=PaddingMode.UNITIZE, right=PaddingMode.EXTEND
    )
    assert len(padded) == 49 and padded[:12] == (1,) * 12
    assert padded[12:24] == values
    assert padded[-1] == pytest.approx(1.710339358)


def test_pert_allocation_preserves_mass_without_padding_observations():
    periods = make_periods(date(2000, 1, 1), frequency=Frequency.MONTH, count=12)
    flow = projection.distribute(
        Quantity(magnitude=1, units="meter"),
        periods=periods,
        distribution=Distribution.pert(),
    )
    assert flow.total().magnitude == pytest.approx(1)
    assert tuple(m.period for m in flow.movements) == periods
