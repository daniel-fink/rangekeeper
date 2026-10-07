"""Construct half-open periods from explicit anchors and calendar grids."""

from __future__ import annotations

from datetime import date, timedelta
from collections.abc import Sequence

from ..model.duration import Period, Span
from .calendar import (
    Frequency,
    MonthRoll,
    PeriodTiming,
    elapsed_days,
    measure,
    offset,
    require_date,
)


def make_period(start_inclusive: date, end_exclusive: date) -> Period:
    """Construct a positive interval; convert old inclusive end dates explicitly."""
    return Period(
        start_inclusive=require_date(start_inclusive),
        end_exclusive=require_date(end_exclusive),
    ).check()


def make_periods(
    start: date,
    *,
    frequency: Frequency,
    count: int,
    month_roll: MonthRoll = MonthRoll.PRESERVE_END,
) -> tuple[Period, ...]:
    """Create adjacent periods using cumulative offsets from the original anchor."""
    offset(start, frequency=frequency, count=0, month_roll=month_roll)
    if type(count) is not int or count < 0:
        raise ValueError("period count must be a nonnegative integer")
    boundaries = [
        offset(start, frequency=frequency, count=i, month_roll=month_roll)
        for i in range(count + 1)
    ]
    return tuple(make_period(a, b) for a, b in zip(boundaries, boundaries[1:]))


def periods_between(
    start_inclusive: date,
    end_exclusive: date,
    *,
    frequency: Frequency,
    include_partial: bool = False,
    month_roll: MonthRoll = MonthRoll.PRESERVE_END,
) -> tuple[Period, ...]:
    """Partition an interval; require explicit permission for a partial final period."""
    if elapsed_days(start_inclusive, end_exclusive) < 0:
        raise ValueError("end precedes start")
    offset(start_inclusive, frequency=frequency, count=0, month_roll=month_roll)
    if type(include_partial) is not bool:
        raise TypeError("include_partial must be a Boolean")
    count = measure(
        start_inclusive, end_exclusive, frequency=frequency, month_roll=month_roll
    )
    result = make_periods(
        start_inclusive, frequency=frequency, count=count, month_roll=month_roll
    )
    previous = result[-1].end_exclusive if result else start_inclusive
    if previous < end_exclusive:
        if not include_partial:
            raise ValueError("span contains a partial final period")
        result += (make_period(previous, end_exclusive),)
    return result


def align(
    value: date,
    *,
    frequency: Frequency,
    week_start: int = 0,
    year_start_month: int = 1,
    origin: date | None = None,
) -> Period:
    """Return the containing calendar period; fortnight and multi-year grids need an origin.

    Weekday zero means Monday. An origin must match the selected weekday or
    fiscal boundary. It defines a continuous grid on both sides of that date.
    """
    offset(value, frequency=frequency, count=0)
    if type(week_start) is not int or not 0 <= week_start <= 6:
        raise ValueError("week_start must be an integer from zero to six")
    if type(year_start_month) is not int or not 1 <= year_start_month <= 12:
        raise ValueError("year_start_month must be an integer from one to twelve")
    if origin is not None:
        require_date(origin)
    days, months = frequency.step
    if days:
        if year_start_month != 1:
            raise ValueError("year_start_month applies only to month-based grids")
        if frequency is Frequency.DAY:
            if origin is not None or week_start != 0:
                raise ValueError("day alignment needs no origin or weekday")
            start = value
        else:
            if origin is not None and origin.weekday() != week_start:
                raise ValueError("origin conflicts with week_start")
            if frequency is Frequency.BIWEEK:
                if origin is None:
                    raise ValueError("biweek alignment requires an explicit origin")
                start = origin + timedelta(days=((value - origin).days // days) * days)
            else:
                start = value - timedelta(days=(value.weekday() - week_start) % 7)
        return make_period(start, start + timedelta(days=days))
    if week_start != 0:
        raise ValueError("week_start applies only to week grids")
    if months > 12:
        if origin is None:
            raise ValueError("multi-year alignment requires an explicit origin")
        if origin.day != 1 or origin.month != year_start_month:
            raise ValueError("origin conflicts with year_start_month")
        anchor = origin.year * 12 + origin.month - 1
    else:
        if origin is not None:
            raise ValueError("origin applies only to fortnight or multi-year grids")
        if frequency is Frequency.MONTH and year_start_month != 1:
            raise ValueError("month alignment needs no fiscal year start")
        anchor = year_start_month - 1
    index = value.year * 12 + value.month - 1
    first = anchor + ((index - anchor) // months) * months
    year, month = divmod(first, 12)
    start = date(year, month + 1, 1)
    return make_period(start, offset(start, frequency=frequency))


def cover(periods: Sequence[Period], *, name: str | None = None) -> Span:
    """Return a Span covering all intervals, including gaps between them."""
    if not periods:
        raise ValueError("cover requires at least one interval")
    for period in periods:
        period.check()
    return Span(
        start_inclusive=min(p.start_inclusive for p in periods),
        end_exclusive=max(p.end_exclusive for p in periods),
        name=name,
    )
