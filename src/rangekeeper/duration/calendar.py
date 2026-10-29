"""Date offsets and whole-step measurement with explicit calendar rules."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from enum import Enum, unique


@unique
class Frequency(Enum):
    """Select the calendar step of a date grid, from one day to one decade."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    HALFYEAR = "halfyear"
    YEAR = "year"
    BIENNIUM = "biennium"
    QUINQUENNIUM = "quinquennium"
    DECADE = "decade"

    @property
    def step(self) -> tuple[int, int]:
        """Return calendar days and months; exactly one component is nonzero."""
        return _STEPS[self]


_STEPS = dict(
    zip(
        Frequency,
        (
            (1, 0),
            (7, 0),
            (0, 1),
            (0, 3),
            (0, 6),
            (0, 12),
            (0, 24),
            (0, 60),
            (0, 120),
        ),
        strict=True,
    )
)


@unique
class MonthRoll(Enum):
    """Select how a month step treats a day that the target month does not have."""

    PRESERVE_END = "preserve_end"
    CLAMP = "clamp"


@unique
class PeriodTiming(Enum):
    """Select the date that represents a Period: first day, last day or end boundary."""

    FIRST = "first"
    LAST = "last"
    END = "end"


@unique
class DayCount(Enum):
    """Select the day-count convention of a year fraction."""

    ACTUAL_365 = "actual/365"
    ACTUAL_360 = "actual/360"
    ACTUAL_ACTUAL = "actual/actual"
    THIRTY_360 = "30/360"


def require_date(value: date) -> date:
    """Require a calendar date; never truncate a datetime or timezone."""
    if type(value) is not date:
        raise TypeError("coordinate must be a calendar date, not a datetime")
    return value


def offset(
    value: date,
    *,
    frequency: Frequency,
    count: int = 1,
    month_roll: MonthRoll = MonthRoll.PRESERVE_END,
) -> date:
    """Apply steps from the supplied anchor, preserving its month-end rule."""
    require_date(value)
    if not isinstance(frequency, Frequency):
        raise TypeError("frequency must be a Frequency")
    if not isinstance(month_roll, MonthRoll):
        raise TypeError("month_roll must be a MonthRoll")
    if type(count) is not int:
        raise TypeError("count must be an integer")
    days, months = frequency.step
    if days:
        return value + timedelta(days=count * days)
    if count == 0:
        return value
    index = value.year * 12 + value.month - 1 + months * count
    year, month = divmod(index, 12)
    month += 1
    last = calendar.monthrange(year, month)[1]
    preserve = (
        month_roll is MonthRoll.PRESERVE_END
        and value.day == calendar.monthrange(value.year, value.month)[1]
    )
    return value.replace(
        year=year, month=month, day=last if preserve else min(value.day, last)
    )


def elapsed_days(start: date, end: date) -> int:
    """Return signed whole calendar days; both endpoints must be dates."""
    return (require_date(end) - require_date(start)).days


def count_steps(
    start: date,
    end: date,
    *,
    frequency: Frequency,
    month_roll: MonthRoll = MonthRoll.PRESERVE_END,
) -> int:
    """Count complete anchored steps, negating the forward count for reversed dates.

    Calendar clamping loses information, so this does not invert every negative
    offset. It counts steps from the earlier endpoint, not calendar bins crossed.
    """
    difference = elapsed_days(start, end)
    offset(start, frequency=frequency, count=0, month_roll=month_roll)
    if difference < 0:
        return -count_steps(end, start, frequency=frequency, month_roll=month_roll)
    days, months = frequency.step
    if days:
        return difference // days
    count = ((end.year - start.year) * 12 + end.month - start.month) // months
    if offset(start, frequency=frequency, count=count, month_roll=month_roll) > end:
        count -= 1
    return count


def year_fraction(start: date, end: date, *, convention: DayCount) -> float:
    """Return the signed year fraction; actual/actual is ISDA, 30/360 is 30E/360."""
    if not isinstance(convention, DayCount):
        raise TypeError("convention must be a DayCount")
    start, end = require_date(start), require_date(end)
    if end < start:
        return -year_fraction(end, start, convention=convention)
    if convention is DayCount.ACTUAL_365:
        return (end - start).days / 365
    if convention is DayCount.ACTUAL_360:
        return (end - start).days / 360
    if convention is DayCount.THIRTY_360:
        days = (
            360 * (end.year - start.year)
            + 30 * (end.month - start.month)
            + min(end.day, 30)
            - min(start.day, 30)
        )
        return days / 360
    # Actual/actual ISDA: days in each calendar year over that year's length.
    fraction = 0.0
    for year in range(start.year, end.year + 1):
        lower = max(start, date(year, 1, 1))
        upper = min(end, date(year + 1, 1, 1))
        fraction += (upper - lower).days / (366 if calendar.isleap(year) else 365)
    return fraction
