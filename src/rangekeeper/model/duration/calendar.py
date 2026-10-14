"""Date offsets and whole-step measurement with explicit calendar rules."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from enum import Enum, unique
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyxirr import DayCount as FinancialDayCount


@unique
class Frequency(Enum):
    DAY = "day"
    WEEK = "week"
    BIWEEK = "biweek"
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
            (14, 0),
            (0, 1),
            (0, 3),
            (0, 6),
            (0, 12),
            (0, 24),
            (0, 60),
            (0, 120),
        ),
    )
)


@unique
class MonthRoll(Enum):
    PRESERVE_END = "preserve_end"
    CLAMP = "clamp"


@unique
class PeriodTiming(Enum):
    FIRST = "first"
    LAST = "last"
    END = "end"


@unique
class DayCount(Enum):
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


def measure(
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
        return -measure(end, start, frequency=frequency, month_roll=month_roll)
    days, months = frequency.step
    if days:
        return difference // days
    count = ((end.year - start.year) * 12 + end.month - start.month) // months
    if offset(start, frequency=frequency, count=count, month_roll=month_roll) > end:
        count -= 1
    return count


def year_fraction(start: date, end: date, *, convention: DayCount) -> float:
    """Use PyXIRR: actual/actual is ISDA; 30/360 is European 30E/360."""
    import pyxirr

    return pyxirr.year_fraction(
        require_date(start), require_date(end), resolve_day_count(convention)
    )


def resolve_day_count(convention: DayCount) -> FinancialDayCount:
    """Map one shared convention to the financial backend, loaded on demand."""
    if not isinstance(convention, DayCount):
        raise TypeError("convention must be a DayCount")
    import pyxirr

    return {
        DayCount.ACTUAL_365: pyxirr.DayCount.ACT_365F,
        DayCount.ACTUAL_360: pyxirr.DayCount.ACT_360,
        DayCount.ACTUAL_ACTUAL: pyxirr.DayCount.ACT_ACT_ISDA,
        DayCount.THIRTY_360: pyxirr.DayCount.THIRTY_E_360,
    }[convention]
