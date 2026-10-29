"""Calendar grids, and the Period of a grid that contains a date."""

from calendar import Day, Month
from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from rangekeeper.duration import (
    DayGrid,
    Frequency,
    MonthGrid,
    MultiYearGrid,
    WeekGrid,
    containing_period,
)
from rangekeeper.errors import ContractError


@pytest.mark.parametrize(
    "grid,expected",
    [
        (DayGrid(), (date(2026, 8, 20), date(2026, 8, 21))),
        (WeekGrid(), (date(2026, 8, 17), date(2026, 8, 24))),
        (WeekGrid(starts=Day.SUNDAY), (date(2026, 8, 16), date(2026, 8, 23))),
        (WeekGrid(starts=Day.THURSDAY), (date(2026, 8, 20), date(2026, 8, 27))),
        (MonthGrid(frequency=Frequency.MONTH), (date(2026, 8, 1), date(2026, 9, 1))),
        (
            MonthGrid(frequency=Frequency.QUARTER),
            (date(2026, 7, 1), date(2026, 10, 1)),
        ),
        (
            MonthGrid(frequency=Frequency.HALFYEAR),
            (date(2026, 7, 1), date(2027, 1, 1)),
        ),
        (MonthGrid(frequency=Frequency.YEAR), (date(2026, 1, 1), date(2027, 1, 1))),
    ],
)
def test_each_grid_gives_the_period_that_contains_a_date(grid, expected):
    result = containing_period(on=date(2026, 8, 20), grid=grid)
    assert (result.first, result.end) == expected


def test_a_month_grid_divides_a_year_that_starts_in_one_month():
    def fiscal(frequency, on):
        grid = MonthGrid(frequency=frequency, year_starts=Month.JULY)
        return containing_period(on=on, grid=grid)

    year = fiscal(Frequency.YEAR, date(2026, 3, 3))
    assert (year.first, year.end) == (date(2025, 7, 1), date(2026, 7, 1))
    half = fiscal(Frequency.HALFYEAR, date(2026, 3, 3))
    assert (half.first, half.end) == (date(2026, 1, 1), date(2026, 7, 1))
    quarter = fiscal(Frequency.QUARTER, date(2026, 6, 30))
    assert (quarter.first, quarter.last, quarter.end) == (
        date(2026, 4, 1),
        date(2026, 6, 30),
        date(2026, 7, 1),
    )
    # Each year start gives the same months.
    assert fiscal(Frequency.MONTH, date(2026, 3, 3)) == containing_period(
        on=date(2026, 3, 3), grid=MonthGrid(frequency=Frequency.MONTH)
    )


@pytest.mark.parametrize(
    "frequency,first,end",
    [
        (Frequency.BIENNIUM, date(2025, 7, 1), date(2027, 7, 1)),
        (Frequency.QUINQUENNIUM, date(2026, 7, 1), date(2031, 7, 1)),
        (Frequency.DECADE, date(2021, 7, 1), date(2031, 7, 1)),
    ],
)
def test_a_multiyear_grid_continues_on_both_sides_of_its_origin(frequency, first, end):
    grid = MultiYearGrid(frequency=frequency, origin=date(2021, 7, 1))
    period = containing_period(on=date(2026, 8, 1), grid=grid)
    assert (period.first, period.end) == (first, end)
    assert containing_period(on=period.end, grid=grid).first == end
    assert containing_period(on=date(2021, 6, 30), grid=grid).end == date(2021, 7, 1)


def test_a_grid_takes_only_the_choices_that_apply_to_it():
    # A week has no origin (#403: WeekGrid ignored one), a day has no weekday
    # and a year within a MonthGrid has no origin.
    with pytest.raises(TypeError):
        WeekGrid(origin=date(2026, 1, 5))
    with pytest.raises(TypeError):
        DayGrid(starts=Day.MONDAY)
    with pytest.raises(TypeError):
        MonthGrid(frequency=Frequency.YEAR, origin=date(2026, 1, 1))
    with pytest.raises(TypeError):
        MultiYearGrid(
            frequency=Frequency.DECADE,
            origin=date(2021, 7, 1),
            year_starts=Month.JULY,
        )


def test_a_grid_checks_its_choices_when_it_is_made():
    with pytest.raises(ContractError, match="MonthGrid takes MONTH") as error:
        MonthGrid(frequency=Frequency.DECADE)
    assert error.value.values == {"grid": "MonthGrid", "frequency": "decade"}
    for frequency in (Frequency.DAY, Frequency.WEEK, Frequency.YEAR):
        with pytest.raises(ContractError, match="MultiYearGrid takes BIENNIUM"):
            MultiYearGrid(frequency=frequency, origin=date(2021, 7, 1))
    with pytest.raises(ContractError, match="first day of a month"):
        MultiYearGrid(frequency=Frequency.DECADE, origin=date(2021, 7, 2))
    with pytest.raises(TypeError, match="calendar.Day"):
        WeekGrid(starts=0)
    with pytest.raises(TypeError, match="calendar.Month"):
        MonthGrid(frequency=Frequency.YEAR, year_starts=7)
    with pytest.raises(TypeError, match="Frequency"):
        MonthGrid(frequency="year")
    with pytest.raises(TypeError, match="datetime"):
        MultiYearGrid(frequency=Frequency.DECADE, origin=datetime(2021, 7, 1))


def test_containing_period_names_its_arguments():
    with pytest.raises(TypeError, match="grid must be"):
        containing_period(on=date(2026, 1, 1), grid=Frequency.YEAR)
    with pytest.raises(TypeError, match="datetime"):
        containing_period(on=datetime(2026, 1, 1), grid=DayGrid())
    with pytest.raises(TypeError):
        containing_period(date(2026, 1, 1), grid=DayGrid())


def test_grids_are_frozen_values():
    grid = WeekGrid(starts=Day.SUNDAY)
    assert grid == WeekGrid(starts=Day.SUNDAY) != WeekGrid()
    assert hash(grid) == hash(WeekGrid(starts=Day.SUNDAY))
    assert DayGrid().frequency is Frequency.DAY and grid.frequency is Frequency.WEEK
    with pytest.raises(FrozenInstanceError):
        grid.starts = Day.MONDAY
