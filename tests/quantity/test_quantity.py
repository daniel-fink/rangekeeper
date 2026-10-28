"""Quantity text, conversion and unit-checked arithmetic (D13, D17)."""

from decimal import Decimal

import pytest

import rangekeeper as rk
from rangekeeper.errors import UnitError
from rangekeeper.quantity import Quantity


def test_text_and_magnitude_make_the_same_quantity():
    assert rk.Quantity is Quantity
    assert Quantity(text="7 % pa") == Quantity(magnitude=7.0, units="% pa")
    assert Quantity(text="20e6 AUD").magnitude == Decimal("20000000")
    assert Quantity(text="1200 USD pa").units == "USD pa"


@pytest.mark.parametrize(
    "arguments",
    [
        {"text": "5 %", "magnitude": 5},
        {"text": "5 %", "units": "%"},
        {"magnitude": 5},
        {"units": "%"},
        {},
    ],
)
def test_text_or_magnitude_and_units(arguments):
    with pytest.raises(TypeError):
        Quantity(**arguments)


def test_text_is_checked_with_suggestions():
    with pytest.raises(UnitError) as error:
        Quantity(text="5 pct")
    assert "%" in error.value.suggestions
    with pytest.raises(UnitError, match="0.005 dwelling per sqm"):
        Quantity(text="0.5 dwelling per 100 sqm")
    with pytest.raises(TypeError):
        Quantity("5 %")  # type: ignore[misc]


def test_repr_and_text_read_back():
    for text in ("1200 USD pa", "0.02 dimensionless", "-105.5 USD", "7 % pa"):
        quantity = Quantity(text=text)
        assert str(quantity) == text
        assert repr(quantity) == f"Quantity(text={text!r})"
        assert Quantity(text=str(quantity)) == quantity


def test_to_converts_compatible_units():
    rent = Quantity(text="1200 USD pa").to(units="USD per month")
    assert rent.units == "USD per month"
    assert rent.magnitude == pytest.approx(100)
    with pytest.raises(UnitError):
        Quantity(text="1 USD").to(units="AUD")


def test_a_rate_per_year_times_a_year_is_a_ratio():
    product = Quantity(text="2 % pa") * Quantity(text="1 year")
    assert product.units == "dimensionless"
    assert product.magnitude == pytest.approx(0.02)


def test_dimensionless_operands_act_as_plain_numbers():
    price = Quantity(text="105 USD") / Quantity(text="5 %")
    assert price == Quantity(text="2100 USD")
    assert Quantity(text="100 USD") * Quantity(text="5 %") == Quantity(text="5 USD")
    assert (Quantity(text="5 %") * Quantity(text="100 sqm")).units == "sqm"


def test_units_combine_and_cancel():
    rent = Quantity(text="750 AUD per sqm pa") * Quantity(text="100 sqm")
    assert rent == Quantity(text="75000 AUD * pa")
    assert Quantity(text="75000 AUD pa") * Quantity(text="2 years") == Quantity(
        text="150000 AUD"
    )
    rate = Quantity(text="6 AUD per month") / Quantity(text="1000 AUD")
    assert rate.units == "per month"
    assert rate.to(units="% pa").magnitude == pytest.approx(7.2)
    assert (1 / Quantity(text="4 year")).units == "per year"


def test_numbers_scale_and_currency_stays_an_amount():
    amount = Quantity(text="105.5 USD")
    assert 2 * amount == amount * 2 == Quantity(text="211 USD")
    assert (amount / 1.07).magnitude == Decimal("98.5981308411215")
    assert -amount == Quantity(text="-105.5 USD")
    assert abs(-amount) == amount
    assert isinstance((amount * 0.5).magnitude, Decimal)


def test_addition_needs_compatible_units():
    assert Quantity(text="100 m") + Quantity(text="1 km") == Quantity(text="1100 m")
    assert Quantity(text="3 USD") - Quantity(text="1 USD") == Quantity(text="2 USD")
    with pytest.raises(UnitError):
        Quantity(text="1 USD") + Quantity(text="1 AUD")
    with pytest.raises(TypeError):
        Quantity(text="1 USD") + 1  # type: ignore[operator]


def test_a_nonfinite_result_raises():
    with pytest.raises(UnitError, match="non-finite"):
        Quantity(text="1e300 m") * 1e300
