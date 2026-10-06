"""Construct half-open date intervals and resolve explicitly selected boundary dates."""

from __future__ import annotations

from datetime import date, timedelta
from collections.abc import Sequence
from typing import Literal

from ..model.duration import Period, Span
from .calendar import Frequency, elapsed_days, offset, require_date

PeriodTiming = Literal["start", "last_day", "end"]


def make_period(start: date, end: date) -> Period:
    """Construct [start, end); convert old inclusive end dates explicitly."""
    result = Period(start=require_date(start), end=require_date(end))
    result.check()
    return result


def make_periods(
    start: date, *, frequency: Frequency, count: int, month_end: bool = False
) -> tuple[Period, ...]:
    """Create adjacent date periods from one anchor, including irregular months."""
    require_date(start)
    if type(count) is not int or count < 0:
        raise ValueError("period count must be a nonnegative integer")
    boundaries = [start] + [
        offset(start, frequency=frequency, count=i, month_end=month_end)
        for i in range(1, count + 1)
    ]
    return tuple(make_period(a, b) for a, b in zip(boundaries, boundaries[1:]))


def periods_between(
    start: date, end: date, *, frequency: Frequency, include_partial: bool = False
) -> tuple[Period, ...]:
    """Partition [start, end); include a partial final period only when requested."""
    if elapsed_days(start, end) < 0:
        raise ValueError("end precedes start")
    result, previous, index = [], start, 1
    while previous < end:
        boundary = offset(start, frequency=frequency, count=index)
        if boundary > end:
            if not include_partial:
                raise ValueError("span contains a partial final period")
            boundary = end
        result.append(make_period(previous, boundary))
        previous, index = boundary, index + 1
    return tuple(result)


def cover(periods: Sequence[Period], *, name: str | None = None) -> Span:
    """Return a Span covering all intervals, including gaps between them."""
    if not periods:
        raise ValueError("cover requires at least one interval")
    for period in periods:
        period.check()
    return Span(
        start=min(p.start for p in periods), end=max(p.end for p in periods), name=name
    )
