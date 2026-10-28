"""rk.duration.Periods and the Span conveniences (G01, D25)."""

from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.duration import Frequency, MonthRoll, Period, Periods, Span
from rangekeeper.errors import MissingReferenceError, UnitError
from rangekeeper.quantity import Quantity

START = date(2001, 1, 1)


def test_span_from_a_length():
    holding = Span(start=START, length="10 years", name="Holding")
    assert holding == Span(name="Holding", start=START, end=date(2011, 1, 1))
    assert Span(start=START, length=Quantity(text="6 months")).end == date(2001, 7, 1)
    assert Span(start=START, length="2 quarters").end == date(2001, 7, 1)
    assert Span(start=START, length="3 weeks").end == date(2001, 1, 22)
    assert Span(start=START, length="1 day").end == date(2001, 1, 2)
    assert Span(start=date(2001, 1, 31), length="1 month").end == date(2001, 2, 28)


@pytest.mark.parametrize("length", ["1.5 years", "0 years", "-1 year", "10 sqm"])
def test_a_length_is_a_positive_whole_number_of_calendar_steps(length):
    with pytest.raises(UnitError):
        Span(start=START, length=length)


def test_span_needs_an_end_or_a_length():
    with pytest.raises(TypeError):
        Span(start=START)
    with pytest.raises(TypeError):
        Span(start=START, end=date(2002, 1, 1), length="1 year")


def test_extend_keeps_the_start_and_drops_the_name():
    holding = Span(start=START, length="10 years", name="Holding")
    forecast = holding.extend(by="1 year")
    assert forecast == Span(start=START, end=date(2012, 1, 1))
    assert forecast.name is None
    assert holding.extend(by="1 year", name="Forecast").name == "Forecast"


def test_span_periods_returns_periods():
    years = Span(start=START, length="11 years").periods(frequency=Frequency.YEAR)
    assert isinstance(years, Periods)
    assert rk.duration.Periods is Periods
    assert len(years) == 11
    assert years.start == START and years.end == date(2012, 1, 1)
    assert years.frequency is Frequency.YEAR
    assert years.span == Span(start=START, end=date(2012, 1, 1))
    assert years[0] == Period(start=START, end=date(2002, 1, 1))
    assert years[-1] == Period(start=date(2011, 1, 1), end=date(2012, 1, 1))
    assert list(years)[3] == years[3]
    assert repr(years) == (
        "Periods(start=2001-01-01, end=2012-01-01, frequency=year, count=11)"
    )
    with pytest.raises(TypeError):
        Span(start=START, length="1 year").periods(Frequency.YEAR)  # type: ignore[misc]


def test_periods_equality_slices_and_construction():
    years = Periods(start=START, frequency=Frequency.YEAR, count=4)
    assert years == Span(start=START, length="4 years").periods(
        frequency=Frequency.YEAR
    )
    assert years != Periods(start=START, frequency=Frequency.YEAR, count=3)
    assert years[1:3] == Periods(
        start=date(2002, 1, 1), frequency=Frequency.YEAR, count=2
    )
    assert len(years[3:1]) == 0
    with pytest.raises(ValueError):
        years[::2]
    with pytest.raises(AttributeError):
        years._first = 2  # type: ignore[misc]


def test_trim_extend_and_containing():
    years = Periods(start=START, frequency=Frequency.YEAR, count=11)
    holding = Span(start=START, length="10 years")
    assert years.trim(span=holding) == years[:10]
    assert years.trim(span=years[4]) == years[4:5]
    assert len(years.trim(span=Span(start=date(1990, 1, 1), length="1 year"))) == 0
    with pytest.raises(ValueError, match="crosses"):
        years.trim(span=Span(start=date(2001, 6, 1), length="1 year"))
    assert years[:10].extend(count=1) == years
    assert years.containing(on=date(2005, 6, 30)) == years[4]
    with pytest.raises(MissingReferenceError):
        years.containing(on=date(2020, 1, 1))


def test_extend_keeps_the_month_end_anchor():
    months = Periods(
        start=date(2001, 1, 31),
        frequency=Frequency.MONTH,
        count=1,
        month_roll=MonthRoll.PRESERVE_END,
    )
    assert [p.end for p in months.extend(count=2)] == [
        date(2001, 2, 28),
        date(2001, 3, 31),
        date(2001, 4, 30),
    ]
    assert months.extend(count=2)[1:].extend(count=1)[-1].end == date(2001, 5, 31)


def test_a_partial_final_period_cannot_extend():
    span = Span(start=START, end=date(2002, 6, 1))
    periods = span.periods(frequency=Frequency.YEAR, include_partial=True)
    assert periods[-1] == Period(start=date(2002, 1, 1), end=date(2002, 6, 1))
    with pytest.raises(ValueError, match="partial"):
        periods.extend(count=1)
