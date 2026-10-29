"""Currency amounts in records and at the float64 boundary (ADR-023)."""

import random
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

import pytest

from rangekeeper import money
from rangekeeper.errors import Code
from rangekeeper.flow import Flow, Movement
from rangekeeper.quantity import Quantity, default_units
from rangekeeper.schema.runtime import exact_equal
from rangekeeper.shared.encoding import encode
from rangekeeper.shared.errors import (
    ContractError,
    NumericalError,
    UnitError,
    ValidationError,
)

DAYS = (date(2027, 1, 1), date(2027, 2, 1), date(2027, 3, 1))


def code(error):
    return error.value.report.issues[0].code


def test_a_currency_amount_is_decimal_and_its_data_is_canonical_text():
    quantity = Quantity(magnitude=Decimal("1.50"), units="AUD")
    assert quantity.to_data()["magnitude"] == "1.5"
    assert quantity.magnitude == Decimal("1.5")
    assert quantity.number == 1.5
    assert Quantity(magnitude=0.1 + 0.2, units="AUD").magnitude == Decimal("0.3")
    assert Quantity(magnitude=Decimal("-0"), units="AUD").to_data()["magnitude"] == "0"
    assert Quantity(magnitude="1250000.50", units="AUD").magnitude == Decimal(
        "1250000.5"
    )
    assert Quantity(magnitude=12, units="JPY").to_data()["magnitude"] == "12"
    assert Quantity(magnitude=Decimal("1E+3"), units="AUD").to_data() == {
        "magnitude": "1000",
        "units": "AUD",
    }


def test_other_magnitudes_stay_numbers():
    area = Quantity(magnitude=1.5, units="m^2")
    assert type(area.magnitude) is float and area.magnitude == 1.5
    rate = Quantity(magnitude=450.5, units="AUD/m^2")
    assert rate.to_data()["magnitude"] == 450.5
    assert type(Quantity(magnitude=3, units="m").magnitude) is int


@pytest.mark.parametrize("magnitude", [Decimal("1.5"), "1.5"])
def test_decimal_text_in_other_units_fails(magnitude):
    with pytest.raises(ValidationError) as error:
        Quantity(magnitude=magnitude, units="m^2")
    assert code(error) == Code.CURRENCY_AMOUNT


def test_more_than_fifteen_significant_digits_fails():
    with pytest.raises(ValidationError) as error:
        Quantity(magnitude=Decimal("1234567890.123456"), units="AUD")
    assert code(error) == Code.AMOUNT_DIGITS
    assert Quantity(magnitude=Decimal("123456789012345000"), units="AUD")
    assert Quantity(magnitude=Decimal("0.000000000000000000123"), units="AUD")


@pytest.mark.parametrize("units", ["AUD", "m^2"])
@pytest.mark.parametrize(
    "magnitude",
    [float("nan"), float("inf"), Decimal("NaN"), Decimal("-Infinity"), True],
)
def test_non_finite_and_boolean_magnitudes_fail(units, magnitude):
    with pytest.raises((ValueError, TypeError)):
        Quantity(magnitude=magnitude, units=units)


def test_scaled_currency_units_suggest_the_code():
    with pytest.raises(UnitError) as error:
        default_units.validate_units("kAUD")
    assert error.value.suggestions == ("AUD",)


def test_a_float_movement_in_currency_data_fails():
    data = {
        "units": "AUD",
        "movements": [{"id": str(uuid4()), "date": "2027-01-01", "magnitude": 1.5}],
    }
    with pytest.raises(ValidationError) as error:
        Flow.from_data(data)
    assert code(error) == Code.CURRENCY_AMOUNT
    data["movements"][0]["magnitude"] = "1.5"
    assert Flow.from_data(data).movements[0].magnitude == Decimal("1.5")


def test_flow_construction_converts_floats_in_currency_units():
    flow = Flow.from_events(DAYS, (0.1, 2, "3.50"), units="AUD")
    assert [m.to_data()["magnitude"] for m in flow.movements] == ["0.1", "2", "3.5"]
    other = Flow.from_events(DAYS, (0.1, 2, None), units="m^2")
    assert [m.magnitude for m in other.movements] == [0.1, 2, None]


def test_the_boundary_round_trips_every_valid_amount():
    generator = random.Random(117)
    for _ in range(100_000):
        digits = generator.randint(1, 15)
        unscaled = generator.randrange(10 ** (digits - 1), 10**digits)
        amount = Decimal(unscaled).scaleb(-generator.randint(0, 20))
        amount = -amount if generator.random() < 0.5 else amount
        assert money.to_amount(money.to_number(amount)) == amount


def test_to_amount_rounds_to_fifteen_digits_and_rejects_non_finite():
    assert money.to_amount(1000 * 1.03**12) == Decimal("1425.76088684618")
    assert money.to_amount(0.1 + 0.2) == Decimal("0.3")
    assert money.to_amount(3.2e-11) == Decimal("0.000000000032")
    for value in (float("nan"), float("inf")):
        with pytest.raises(NumericalError):
            money.to_amount(value)


def test_sums_use_float64_and_give_one_amount():
    flow = Flow.from_events(DAYS, ("0.10", "0.10", "0.10"), units="AUD")
    total = flow.total()
    assert total is not None and total.magnitude == Decimal("0.3")
    split = Flow.from_events(DAYS, ("100",) * 3, units="AUD").scale(1 / 3)
    assert {m.magnitude for m in split.movements} == {Decimal("33.3333333333333")}


def test_copies_keep_each_amount_exactly():
    flow = Flow.from_events(
        DAYS, ("1250000.5", "-0.01", "33.3333333333333"), units="AUD"
    )
    for result in (
        flow.clone(),
        flow.clean(),
        flow.trim(span=_span()),
        flow.convert(units="AUD"),
    ):
        assert [m.magnitude for m in result.movements] == [
            m.magnitude for m in flow.movements
        ]
    negated = flow.negate()
    assert [m.magnitude for m in negated.movements] == [
        Decimal("-1250000.5"),
        Decimal("0.01"),
        Decimal("-33.3333333333333"),
    ]
    assert exact_equal(
        negated.negate().to_data()["movements"][0]["magnitude"], "1250000.5"
    )


def _span():
    from rangekeeper.duration import Span

    return Span(start=date(2026, 1, 1), end=date(2028, 1, 1))


def test_rate_times_area_is_an_amount():
    rate = Quantity(magnitude=450.5, units="AUD/m^2")
    area = Quantity(magnitude=1200, units="m^2")
    units = default_units.multiply(rate.units, area.units)
    product = default_units.convert(
        Quantity(magnitude=rate.number * area.number, units=units), to="AUD"
    )
    assert product.magnitude == Decimal("540600")


def test_rounding_uses_minor_units_and_rounds_only_on_request():
    assert Quantity(magnitude="0.125", units="AUD").round().magnitude == Decimal("0.12")
    assert Quantity(magnitude="0.125", units="AUD").round(
        mode=ROUND_HALF_UP
    ).magnitude == Decimal("0.13")
    assert Quantity(magnitude="1234.5", units="JPY").round().magnitude == Decimal(
        "1234"
    )
    assert Quantity(magnitude="1.2345", units="KWD").round().magnitude == Decimal(
        "1.234"
    )
    assert [money.minor_unit(c) for c in ("AUD", "JPY", "KWD", "CLF")] == [2, 0, 3, 4]
    assert money.minor_unit("XAU") is None
    with pytest.raises(UnitError, match="no minor unit"):
        Quantity(magnitude="1.23456", units="XAU").round()
    with pytest.raises(ContractError) as raised:
        money.round(Decimal("1.5"), "AUD", mode="ROUND_SOMETIMES")
    assert raised.value.values == {"mode": "ROUND_SOMETIMES"}
    assert Quantity(magnitude="1.23456", units="XAU").round(places=3).magnitude == (
        Decimal("1.235")
    )
    assert Quantity(magnitude="1234", units="AUD").round(places=-2).magnitude == (
        Decimal("1200")
    )
    with pytest.raises(UnitError):
        Quantity(magnitude=1.5, units="AUD/m^2").round()
    with pytest.raises(ValueError, match="rounding mode"):
        Quantity(magnitude="1", units="AUD").round(mode="nearest")
    assert Quantity(magnitude="1.234", units="AUD").magnitude == Decimal("1.234")


def test_the_fingerprint_encoding_of_equal_amounts_is_equal():
    assert encode(Decimal("1.50")) == encode(Decimal("1.5")) == ["decimal", "1.5"]
    assert encode(Decimal("-0")) == ["decimal", "0"]


def test_is_currency_reads_plain_codes_only():
    assert money.is_currency("AUD") and money.is_currency("XAU")
    assert not money.is_currency("AUD/year") and not money.is_currency("m^2")


def test_a_standalone_movement_keeps_decimal_text():
    movement = Movement(id=uuid4(), date=DAYS[0], magnitude=Decimal("2.50"))
    assert movement.to_data()["magnitude"] == "2.5"
    assert movement.number == 2.5


def test_flow_and_stream_sums_give_the_same_amount():
    from rangekeeper.flow import Stream

    values = ("0.10", "0.20", "1250000.33")
    first = Flow.from_events(DAYS, values, units="AUD")
    second = Flow.from_events(DAYS, ("0.10", "0.10", "0.10"), units="AUD")
    combined = Stream(flows={"a": first, "b": second}).sum()
    assert [m.magnitude for m in combined.movements] == [
        Decimal("0.2"),
        Decimal("0.3"),
        Decimal("1250000.43"),
    ]
    stream_total = Stream(flows={"a": first}).sum().total()
    assert stream_total is not None and stream_total == first.total()


def test_flow_round_rounds_each_movement():
    split = Flow.from_events(DAYS, ("100",) * 3, units="AUD").scale(1 / 3)
    rounded = split.round()
    assert [m.magnitude for m in rounded.movements] == [Decimal("33.33")] * 3
    assert rounded.total().magnitude == Decimal("99.99")
    assert Flow.from_events(
        DAYS, ("100",) * 3, units="AUD"
    ).total().round().magnitude == (Decimal("300"))
    assert {m.id for m in rounded.movements}.isdisjoint(m.id for m in split.movements)
    gaps = Flow.from_events(DAYS, ("1.005", None, "2"), units="AUD").round()
    assert [m.magnitude for m in gaps.movements] == [Decimal("1"), None, Decimal("2")]
    with pytest.raises(UnitError):
        Flow.from_events(DAYS, (1, 2, 3), units="m^2").round()
