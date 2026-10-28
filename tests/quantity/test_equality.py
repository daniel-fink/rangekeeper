"""Value equality of Quantities and Flows, and rk.quantity.isclose (G06)."""

from datetime import date
from decimal import Decimal

import pytest

import rangekeeper as rk
from rangekeeper.duration import make_periods
from rangekeeper.duration.calendar import Frequency
from rangekeeper.errors import UnitError
from rangekeeper.flow import Flow
from rangekeeper.quantity import Quantity, isclose

YEARS = make_periods(date(2001, 1, 1), frequency=Frequency.YEAR, count=3)


def test_quantities_are_equal_by_value():
    assert Quantity(magnitude=1, units="m") == Quantity(magnitude=1.0, units="m")
    assert Quantity(magnitude="1.50", units="AUD") == Quantity(text="1.5 AUD")
    assert Quantity(text="1 m") != Quantity(text="100 cm")
    assert Quantity(text="1 m") != 1
    with pytest.raises(TypeError):
        hash(Quantity(text="1 m"))


def test_quantities_order_in_compatible_units():
    assert Quantity(text="6.9 % pa") < Quantity(text="7 % pa")
    assert Quantity(text="1 km") > Quantity(text="999 m")
    assert Quantity(text="2 AUD") >= Quantity(text="2 AUD")
    with pytest.raises(UnitError):
        _ = Quantity(text="1 AUD") < Quantity(text="1 USD")


def test_flows_are_equal_by_value_not_identity():
    flow = Flow.from_periods(YEARS, [100, 102, 104.04], units="USD")
    copy = flow.clone()
    assert copy.movements[0].id != flow.movements[0].id
    assert copy == flow
    assert not copy.equivalent(flow)
    assert flow != Flow.from_periods(YEARS, [100, 102, 104.05], units="USD")
    assert flow != Flow.from_periods(YEARS, [100, 102, 104.04], units="AUD")
    assert flow != Flow.from_periods(YEARS[:2], [100, 102], units="USD")
    dated = Flow.from_events([p.start for p in YEARS], [100, 102, 104.04], units="USD")
    assert dated != flow


def test_unresolved_amounts_are_equal_only_to_unresolved_amounts():
    flow = Flow.from_periods(YEARS, [1, None, 3], units="m")
    assert flow == flow.clone()
    assert flow != Flow.from_periods(YEARS, [1, 0, 3], units="m")


def test_isclose_quantities():
    assert rk.quantity.isclose is isclose
    assert isclose(actual=Quantity(text="0.07 pa"), expected=Quantity(text="7 % pa"))
    assert not isclose(
        actual=Quantity(text="7.01 % pa"), expected=Quantity(text="7 % pa")
    )
    assert isclose(
        actual=Quantity(text="100.4 AUD"),
        expected=Quantity(text="100 AUD"),
        tolerance="1 AUD",
    )
    assert isclose(
        actual=Quantity(text="1000.1 m"),
        expected=Quantity(text="1 km"),
        tolerance=Quantity(text="10 cm"),
    )
    assert isclose(
        actual=Quantity(text="101 AUD"),
        expected=Quantity(text="100 AUD"),
        relative=0.01,
    )
    with pytest.raises(UnitError):
        isclose(actual=Quantity(text="1 AUD"), expected=Quantity(text="1 USD"))
    with pytest.raises(ValueError):
        isclose(actual=Quantity(text="1 m"), expected=Quantity(text="1 m"), relative=-1)


def test_isclose_flows():
    flow = Flow.from_periods(YEARS, [100, 102, 104.04], units="USD")
    near = Flow.from_periods(
        YEARS, [100, 102, Decimal("104.040000000001")], units="USD"
    )
    assert near != flow
    assert isclose(actual=near, expected=flow)
    assert not isclose(actual=flow.trim(span=YEARS[0]), expected=flow)
    assert isclose(
        actual=Flow.from_periods(YEARS, [1, None, 3], units="m"),
        expected=Flow.from_periods(YEARS, [100, None, 300], units="cm"),
    )
    assert not isclose(
        actual=Flow.from_periods(YEARS, [1, None, 3], units="m"),
        expected=Flow.from_periods(YEARS, [1, 2, 3], units="m"),
    )
    with pytest.raises(TypeError):
        isclose(actual=flow, expected=Quantity(text="1 USD"))
