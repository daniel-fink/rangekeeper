"""Date values: rk.duration.NEVER and date arithmetic (G15, G50, D26)."""

from datetime import date, datetime

import pytest

import rangekeeper as rk
from rangekeeper.duration import NEVER, Never, shift
from rangekeeper.duration.dates import order, require_date_value
from rangekeeper.errors import UnitError
from rangekeeper.quantity import Quantity

START = date(2027, 1, 1)


def test_never_is_a_one_member_enum_and_not_missing():
    assert rk.duration.NEVER is Never.NEVER
    assert list(Never) == [NEVER]
    assert NEVER is not None
    assert NEVER.value == "never"


@pytest.mark.parametrize(
    ("by", "expected"),
    [
        ("1 year", date(2028, 1, 1)),
        ("2 years", date(2029, 1, 1)),
        ("3 months", date(2027, 4, 1)),
        ("1 quarter", date(2027, 4, 1)),
        ("2 weeks", date(2027, 1, 15)),
        ("10 days", date(2027, 1, 11)),
        ("0 days", START),
        ("-1 year", date(2026, 1, 1)),
        (Quantity(magnitude=18, units="months"), date(2028, 7, 1)),
    ],
)
def test_shift_by_a_whole_calendar_length(by, expected):
    assert shift(START, by=by) == expected


def test_a_month_step_keeps_the_last_day_of_a_month():
    assert shift(date(2027, 1, 31), by="1 month") == date(2027, 2, 28)
    assert shift(date(2027, 2, 28), by="1 month") == date(2027, 3, 31)
    assert shift(date(2027, 1, 30), by="1 month") == date(2027, 2, 28)


def test_never_shifted_is_never():
    assert shift(NEVER, by="1 year") is NEVER
    assert shift(NEVER, by="-3 months") is NEVER


@pytest.mark.parametrize("by", ["1.5 years", "1 AUD", "2", "1 hour"])
def test_a_length_is_a_whole_number_of_calendar_steps(by):
    with pytest.raises(UnitError):
        shift(START, by=by)
    with pytest.raises(UnitError):
        shift(NEVER, by=by)


@pytest.mark.parametrize("value", [None, "2027-01-01", 2027, datetime(2027, 1, 1)])
def test_a_date_value_is_a_calendar_date_or_never(value):
    with pytest.raises(TypeError):
        require_date_value(value)
    with pytest.raises(TypeError):
        shift(value, by="1 year")


def test_never_is_later_than_every_date():
    assert sorted([NEVER, date.max, START], key=order) == [START, date.max, NEVER]
    assert order(NEVER) == order(NEVER)
