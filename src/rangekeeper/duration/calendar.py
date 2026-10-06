"""Date-only calendar offsets and explicit financial day-count fractions.

A calendar month is not a fixed physical duration. Build sequences from their
original anchor so February does not move later month ends.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from pyxirr import DayCount as FinancialDayCount

Frequency = Literal[
    "day",
    "week",
    "biweek",
    "month",
    "quarter",
    "halfyear",
    "year",
    "biennium",
    "quinquennium",
    "decade",
]
DayCount = Literal["actual/365", "actual/360", "actual/actual", "30/360"]
_MONTHS = {
    "month": 1,
    "quarter": 3,
    "halfyear": 6,
    "year": 12,
    "biennium": 24,
    "quinquennium": 60,
    "decade": 120,
}


def require_date(value: date) -> date:
    """Require a calendar date; never silently truncate a datetime or timezone."""
    if type(value) is not date:
        raise TypeError("coordinate must be a calendar date, not a datetime")
    return value


def offset(
    value: date, *, frequency: Frequency, count: int = 1, month_end: bool = False
) -> date:
    """Shift a date; clamp invalid days or explicitly select the target month end."""
    require_date(value)
    if type(count) is not int:
        raise TypeError("count must be an integer")
    if frequency in ("day", "week", "biweek"):
        return value + timedelta(
            days=count * {"day": 1, "week": 7, "biweek": 14}[frequency]
        )
    if frequency not in _MONTHS:
        raise ValueError(f"unsupported frequency: {frequency}")
    index = value.year * 12 + value.month - 1 + _MONTHS[frequency] * count
    year, month = divmod(index, 12)
    month += 1
    last = calendar.monthrange(year, month)[1]
    return value.replace(
        year=year, month=month, day=last if month_end else min(value.day, last)
    )


def elapsed_days(start: date, end: date) -> int:
    """Return signed whole calendar days; both endpoints must be dates."""
    return (require_date(end) - require_date(start)).days


def year_fraction(start: date, end: date, *, convention: DayCount) -> float:
    """Calculate a signed accrual fraction through PyXIRR.

    actual/actual is ISDA; 30/360 is European 30E/360. Calendar offsets and
    period construction do not import the financial dependency.
    """
    import pyxirr

    return pyxirr.year_fraction(
        require_date(start), require_date(end), resolve_day_count(convention)
    )


def resolve_day_count(convention: DayCount) -> FinancialDayCount:
    """Map RK convention names to the same PyXIRR rules for accrual and valuation."""
    import pyxirr

    conventions = {
        "actual/365": pyxirr.DayCount.ACT_365F,
        "actual/360": pyxirr.DayCount.ACT_360,
        "actual/actual": pyxirr.DayCount.ACT_ACT_ISDA,
        "30/360": pyxirr.DayCount.THIRTY_E_360,
    }
    if convention not in conventions:
        raise ValueError(f"unsupported day count: {convention}")
    return conventions[convention]
