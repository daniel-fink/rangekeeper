"""Calendar grids, and the Period of a grid that contains a date.

A grid divides the calendar into Periods of one Frequency. Each kind of grid
takes only the choices that apply to it:

- ``DayGrid()``: days.
- ``WeekGrid(starts=)``: weeks that start on one weekday, Monday by default.
- ``MonthGrid(frequency=, year_starts=)``: months, quarters, half-years or
  years of a year that starts in one month, January by default.
- ``MultiYearGrid(frequency=, origin=)``: bienniums, quinquenniums or decades
  from an origin on the first day of a month.

``containing_period(on=, grid=)`` returns the Period of a grid that contains a
date. Weekdays and months are the ``calendar.Day`` and ``calendar.Month`` enums
of the standard library.
"""

from __future__ import annotations

from calendar import Day, Month
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TypeAlias

from rangekeeper.duration.calendar import (
    Frequency,
    offset,
    require_date,
    require_frequency,
)
from rangekeeper.duration.period import Period
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError

# The steps of a MonthGrid divide one year; the steps of a MultiYearGrid are
# several years.
_PARTS_OF_A_YEAR = (
    Frequency.MONTH,
    Frequency.QUARTER,
    Frequency.HALFYEAR,
    Frequency.YEAR,
)
_SEVERAL_YEARS = (Frequency.BIENNIUM, Frequency.QUINQUENNIUM, Frequency.DECADE)


@dataclass(frozen=True, slots=True, kw_only=True)
class DayGrid:
    """A grid of days."""

    @property
    def frequency(self) -> Frequency:
        """The step of each Period: ``Frequency.DAY``."""
        return Frequency.DAY

    def _first(self, on: date) -> date:
        return on


@dataclass(frozen=True, slots=True, kw_only=True)
class WeekGrid:
    """A grid of weeks that start on one weekday, Monday by default."""

    starts: Day = Day.MONDAY

    def __post_init__(self) -> None:
        if not isinstance(self.starts, Day):
            raise TypeError("starts must be a calendar.Day")

    @property
    def frequency(self) -> Frequency:
        """The step of each Period: ``Frequency.WEEK``."""
        return Frequency.WEEK

    def _first(self, on: date) -> date:
        return on - timedelta(days=(on.weekday() - self.starts) % 7)


@dataclass(frozen=True, slots=True, kw_only=True)
class MonthGrid:
    """A grid of months, quarters, half-years or years.

    The Periods divide a year that starts on the first day of ``year_starts``,
    January by default. Months are the same for each start.
    """

    frequency: Frequency
    year_starts: Month = Month.JANUARY

    def __post_init__(self) -> None:
        _require_step(self.frequency, steps=_PARTS_OF_A_YEAR, grid="MonthGrid")
        if not isinstance(self.year_starts, Month):
            raise TypeError("year_starts must be a calendar.Month")

    def _first(self, on: date) -> date:
        return _first_month(on, origin=self.year_starts - 1, frequency=self.frequency)


@dataclass(frozen=True, slots=True, kw_only=True)
class MultiYearGrid:
    """A grid of bienniums, quinquenniums or decades from an origin.

    The origin is the first day of a month. It starts one Period of the grid,
    and the grid continues on both sides of it.
    """

    frequency: Frequency
    origin: date

    def __post_init__(self) -> None:
        _require_step(self.frequency, steps=_SEVERAL_YEARS, grid="MultiYearGrid")
        require_date(self.origin)
        if self.origin.day != 1:
            raise ContractError(
                f"origin {self.origin.isoformat()} is not the first day of a month",
                code=Code.CONTRACT,
                values={"origin": self.origin.isoformat()},
            )

    def _first(self, on: date) -> date:
        return _first_month(on, origin=_month(self.origin), frequency=self.frequency)


Grid: TypeAlias = DayGrid | WeekGrid | MonthGrid | MultiYearGrid
"""A calendar grid: ``DayGrid``, ``WeekGrid``, ``MonthGrid`` or ``MultiYearGrid``."""


def containing_period(*, on: date, grid: Grid) -> Period:
    """Return the Period of a calendar grid that contains a date.

    For a year that starts in July, the Period of 3 March 2026 is from
    2025-07-01 to 2026-07-01:

        grid = MonthGrid(frequency=Frequency.YEAR, year_starts=Month.JULY)
        containing_period(on=date(2026, 3, 3), grid=grid)
    """
    if not isinstance(grid, Grid):
        raise TypeError("grid must be a DayGrid, WeekGrid, MonthGrid or MultiYearGrid")
    first = grid._first(require_date(on))
    return Period(start=first, end=offset(value=first, frequency=grid.frequency))


def _require_step(
    frequency: Frequency, *, steps: tuple[Frequency, ...], grid: str
) -> None:
    """Require one of the steps that a kind of grid takes."""
    if require_frequency(frequency) not in steps:
        names = ", ".join(step.name for step in steps)
        raise ContractError(
            f"{grid} takes {names}, not {frequency.name}",
            code=Code.CONTRACT,
            values={"grid": grid, "frequency": frequency.value},
        )


def _month(day: date) -> int:
    """Return the months from year zero to the month of a date."""
    return day.year * 12 + day.month - 1


def _first_month(on: date, *, origin: int, frequency: Frequency) -> date:
    """Return the first day of the grid step that contains a date.

    The grid steps by the months of ``frequency`` from the month ``origin``,
    counted as in ``_month``.
    """
    _, months = frequency.step
    first = origin + (_month(on) - origin) // months * months
    year, month = divmod(first, 12)
    return date(year, month + 1, 1)
