"""rk.profile growth and distribution profiles and Flow.from_profile (G70, D12)."""

import math
from datetime import date
from decimal import Decimal

import pytest

import rangekeeper as rk
from rangekeeper.duration import Frequency, Periods, Span
from rangekeeper.flow import Flow
from rangekeeper.model import Distribution
from rangekeeper.profile import (
    Compounding,
    Constant,
    Linear,
    Profile,
    SCurve,
    Uniform,
    profiles,
)
from rangekeeper.quantity import Quantity

YEARS = Periods(start=date(2001, 1, 1), frequency=Frequency.YEAR, count=11)


def test_profile_is_public():
    assert "profile" in rk.__all__
    assert rk.profile.Compounding is Compounding


def test_compounding_starts_from_the_initial_amount():
    pgi = Flow.from_profile(
        profile=Compounding(rate="2 % pa"), periods=YEARS, initial="100 USD"
    )
    assert pgi.units == "USD"
    assert pgi.movements[0].magnitude == Decimal(100)
    assert pgi.at(on=date(2010, 1, 1)) == Quantity(text="119.509256862231 USD")
    assert Compounding(rate=Quantity(text="0.02 pa")) == Compounding(rate="2 % pa")


def test_growth_uses_years_since_the_first_period():
    quarters = Periods(start=date(2001, 1, 1), frequency=Frequency.QUARTER, count=5)
    flow = Flow.from_profile(
        profile=Compounding(rate="10 % pa"), periods=quarters, initial="1 ratio"
    )
    assert flow.movements[4].number == pytest.approx(1.1)
    assert flow.movements[2].number == pytest.approx(math.sqrt(1.1))
    tuple_years = tuple(
        Periods(start=date(2001, 1, 1), frequency=Frequency.YEAR, count=3)
    )
    assert Compounding(rate="10 % pa").factors(periods=tuple_years) == pytest.approx(
        (1, 1.1, 1.21)
    )
    assert Linear(rate="10 % pa").factors(periods=YEARS[:3]) == pytest.approx(
        (1, 1.1, 1.2)
    )
    assert Constant().factors(periods=YEARS[:3]) == (1.0, 1.0, 1.0)


def test_distribution_profiles_keep_the_total():
    build = Span(start=date(2025, 1, 1), length="2 years").periods(
        frequency=Frequency.MONTH
    )
    fees = Flow.from_profile(profile=SCurve(), periods=build, total="3e6 AUD")
    assert fees.total() == Quantity(text="3e6 AUD")
    shares = [m.number for m in fees.movements]
    assert shares == pytest.approx(shares[::-1])
    assert shares[0] < shares[11]
    even = Flow.from_profile(profile=Uniform(), periods=YEARS[:4], total="1 AUD")
    assert [m.magnitude for m in even.movements] == [Decimal("0.25")] * 4
    pert = SCurve(distribution=Distribution.pert()).factors(periods=YEARS[:4])
    assert math.fsum(pert) == pytest.approx(1)
    point = SCurve(distribution=Distribution.uniform(lower=1, upper=1))
    assert point.factors(periods=YEARS[:3]) == (1.0, 0.0, 0.0)


def test_a_profile_refuses_the_wrong_amount():
    with pytest.raises(TypeError, match="takes initial="):
        Flow.from_profile(
            profile=Compounding(rate="2 % pa"), periods=YEARS, total="1 AUD"
        )
    with pytest.raises(TypeError, match="takes total="):
        Flow.from_profile(profile=Uniform(), periods=YEARS, initial="1 AUD")
    with pytest.raises(TypeError):
        Flow.from_profile(profile=Uniform(), periods=YEARS)
    with pytest.raises(TypeError):
        Flow.from_profile(profile=object(), periods=YEARS, total="1 AUD")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Compounding(rate="-100 % pa")
    with pytest.raises(rk.errors.UnitError):
        Compounding(rate="2 AUD")
    with pytest.raises(TypeError):
        Compounding(0.02)  # type: ignore[misc]
    with pytest.raises(ValueError):
        Uniform().factors(periods=())


def test_profiles_register_by_name():
    assert set(profiles.names()) == {
        "constant",
        "linear",
        "compounding",
        "uniform",
        "scurve",
    }
    assert profiles.get("compounding") is Compounding
    registration = profiles.registration("scurve")
    assert registration.qualified_name == "rangekeeper.profiles:scurve"
    assert registration.fingerprint
    for cls in (Constant, Uniform, SCurve):
        assert isinstance(cls(), Profile)
