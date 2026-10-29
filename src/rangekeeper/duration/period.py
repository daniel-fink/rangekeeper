"""Period and Span, and half-open periods from explicit anchors and calendar grids."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date, timedelta
from itertools import pairwise
from typing import overload

from rangekeeper.duration.calendar import (
    Frequency,
    MonthRoll,
    count_steps,
    elapsed_days,
    offset,
    require_date,
)
from rangekeeper.duration.calendar import PeriodTiming as PeriodTiming
from rangekeeper.quantity import Quantity, default_units
from rangekeeper.schema import records
from rangekeeper.schema.kinds import register
from rangekeeper.schema.runtime import UNSET, Unset
from rangekeeper.shared.errors import MissingReferenceError, UnitError

# The calendar unit of each whole-step length, such as "10 years".
_LENGTH_UNITS = (
    ("year", Frequency.YEAR),
    ("quarter", Frequency.QUARTER),
    ("month", Frequency.MONTH),
    ("week", Frequency.WEEK),
    ("day", Frequency.DAY),
)


def length_frequency(units: str) -> Frequency | None:
    """Return the Frequency of calendar length units, such as ``"years"``, or None."""
    parsed = default_units._parse(units)
    for name, frequency in _LENGTH_UNITS:
        if parsed == default_units._parse(name):
            return frequency
    return None


def signed_steps(length: Quantity | str) -> tuple[Frequency, int]:
    """Return the Frequency and signed count of a whole length, such as ``"-1 year"``.

    A length is a whole number of days, weeks, months, quarters or years, as
    a Quantity or its text. Zero and negative counts are permitted.
    """
    quantity = Quantity(text=length) if isinstance(length, str) else length
    if not isinstance(quantity, records.Quantity):
        raise TypeError("length must be a Quantity or its text")
    frequency = length_frequency(quantity.units)
    number = float(quantity.magnitude)
    if frequency is None or not number.is_integer():
        raise UnitError(
            f"length {quantity.magnitude} {quantity.units} is not a whole "
            "number of days, weeks, months, quarters or years"
        )
    return frequency, int(number)


def steps(length: Quantity | str) -> tuple[Frequency, int]:
    """Return the Frequency and count of a whole length, such as ``"10 years"``.

    A length is a positive whole number of days, weeks, months, quarters or
    years, as a Quantity or its text.
    """
    frequency, count = signed_steps(length)
    if count <= 0:
        quantity = Quantity(text=length) if isinstance(length, str) else length
        raise UnitError(
            f"length {quantity.magnitude} {quantity.units} is not a positive whole "
            "number of days, weeks, months, quarters or years"
        )
    return frequency, count


@register
class Period(records.Period):
    """Interpret half-open boundaries without storing derived dates."""

    __slots__ = ()

    def __hash__(self) -> int:  # type: ignore[override]
        """Hash the dates, so a Period or Span can key a mapping of amounts."""
        return hash((self._kind, self.start, self.end))

    @property
    def first(self) -> date:
        """Return the first included date."""
        return self.start

    @property
    def last(self) -> date:
        """Return the last included date."""
        return self.end - timedelta(days=1)

    def _invariants(self) -> None:
        """Require a positive date interval [start, end)."""
        if elapsed_days(self.start, self.end) <= 0:
            raise ValueError("period end must follow start")

    def resolve(self, *, timing: PeriodTiming) -> date:
        """Select the first included date, last included date or excluded boundary."""
        if not isinstance(timing, PeriodTiming):
            raise TypeError("timing must be a PeriodTiming")
        return {
            PeriodTiming.FIRST: self.first,
            PeriodTiming.LAST: self.last,
            PeriodTiming.END: self.end,
        }[timing]


@register
class Span(records.Span, Period):
    """A named half-open range of time: it includes its start and excludes its end.

    Give the end, or a ``length`` such as ``"10 years"``:
    ``Span(start=date(2001, 1, 1), length="10 years", name="Holding")``.
    """

    __slots__ = ()

    def __init__(
        self,
        *,
        name: str | None | Unset = UNSET,
        start: date,
        end: date | None = None,
        length: Quantity | str | None = None,
    ) -> None:
        if (end is None) == (length is None):
            raise TypeError("give end or length, not both")
        if length is not None:
            frequency, count = steps(length)
            end = offset(require_date(start), frequency=frequency, count=count)
        assert end is not None
        super().__init__(name=name, start=start, end=end)

    def extend(self, *, by: Quantity | str, name: str | None = None) -> Span:
        """Return a Span with the same start and an end later by a length.

        The new Span has ``name``, by default none.
        """
        frequency, count = steps(by)
        return Span(
            name=UNSET if name is None else name,
            start=self.start,
            end=offset(self.end, frequency=frequency, count=count),
        )

    @classmethod
    def from_duration(
        cls,
        *,
        name: str,
        start: date,
        frequency: Frequency,
        count: int,
        month_roll: MonthRoll | None = None,
    ) -> Span:
        """Create a positive named extent from anchored calendar steps."""
        if type(count) is not int or count <= 0:
            raise ValueError("span count must be a positive integer")
        span = cls(
            name=name,
            start=start,
            end=offset(
                start,
                frequency=frequency,
                count=count,
                month_roll=MonthRoll.PRESERVE_END if month_roll is None else month_roll,
            ),
        )
        return span

    def periods(
        self,
        *,
        frequency: Frequency,
        include_partial: bool = False,
        month_roll: MonthRoll | None = None,
    ) -> Periods:
        """Partition this extent; a partial final period requires explicit permission."""
        roll = MonthRoll.PRESERVE_END if month_roll is None else month_roll
        return Periods._of(
            periods_between(
                self.start,
                self.end,
                frequency=frequency,
                include_partial=include_partial,
                month_roll=roll,
            ),
            frequency=frequency,
            month_roll=roll,
            anchor=self.start,
            first=0,
        )


class Periods(Sequence[Period]):
    """An ordered, gap-free sequence of Periods with one frequency.

    ``Span.periods(frequency=)`` returns one, or make one with
    ``Periods(start=, frequency=, count=)``. Each Period is a calendar step from
    the anchor date, by ``month_roll``. Only a Span partition can end with a
    partial Period. Two Periods are equal when they have the same frequency and
    the same Periods.
    """

    __slots__ = ("_periods", "_frequency", "_month_roll", "_anchor", "_first")

    def __init__(
        self,
        *,
        start: date,
        frequency: Frequency,
        count: int,
        month_roll: MonthRoll = MonthRoll.PRESERVE_END,
    ) -> None:
        self._set(
            make_periods(
                start, frequency=frequency, count=count, month_roll=month_roll
            ),
            frequency=frequency,
            month_roll=month_roll,
            anchor=start,
            first=0,
        )

    @classmethod
    def _of(cls, periods, *, frequency, month_roll, anchor, first) -> Periods:
        result = object.__new__(cls)
        result._set(
            tuple(periods),
            frequency=frequency,
            month_roll=month_roll,
            anchor=anchor,
            first=first,
        )
        return result

    def _set(self, periods, *, frequency, month_roll, anchor, first) -> None:
        if not isinstance(frequency, Frequency):
            raise TypeError("frequency must be a Frequency")
        self._periods: tuple[Period, ...] = periods
        self._frequency: Frequency = frequency
        self._month_roll: MonthRoll = month_roll
        self._anchor: date = anchor
        self._first: int = first

    def __setattr__(self, name, value):
        if hasattr(self, "_first"):
            raise AttributeError("Periods are immutable")
        object.__setattr__(self, name, value)

    @property
    def frequency(self) -> Frequency:
        """The calendar step of each Period."""
        return self._frequency

    @property
    def start(self) -> date:
        """The start of the first Period, or the anchor of an empty sequence."""
        return self._periods[0].start if self._periods else self._step(0)

    @property
    def end(self) -> date:
        """The end of the last Period: the first date after the sequence."""
        return self._periods[-1].end if self._periods else self.start

    @property
    def span(self) -> Span:
        """The Span from the start to the end, without a name."""
        return Span(start=self.start, end=self.end)

    def _step(self, index: int) -> date:
        return offset(
            self._anchor,
            frequency=self._frequency,
            count=self._first + index,
            month_roll=self._month_roll,
        )

    def __len__(self) -> int:
        return len(self._periods)

    def __iter__(self) -> Iterator[Period]:
        return iter(self._periods)

    @overload
    def __getitem__(self, index: int) -> Period: ...

    @overload
    def __getitem__(self, index: slice) -> Periods: ...

    def __getitem__(self, index: int | slice) -> Period | Periods:
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step != 1:
                raise ValueError("a slice of Periods takes every Period")
            return self._slice(start, max(start, stop))
        return self._periods[index]

    def _slice(self, start: int, stop: int) -> Periods:
        return Periods._of(
            self._periods[start:stop],
            frequency=self._frequency,
            month_roll=self._month_roll,
            anchor=self._anchor,
            first=self._first + start,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Periods):
            return NotImplemented
        return self._frequency is other._frequency and self._periods == other._periods

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        if not self._periods:
            return f"Periods(frequency={self._frequency.value}, count=0)"
        return (
            f"Periods(start={self.start.isoformat()}, end={self.end.isoformat()}, "
            f"frequency={self._frequency.value}, count={len(self)})"
        )

    def trim(self, *, span: Period) -> Periods:
        """Return the Periods inside a Period or Span; a partial overlap raises."""
        if not isinstance(span, Period):
            raise TypeError("span must be a Period or Span")
        inside = [
            i
            for i, period in enumerate(self._periods)
            if period.start < span.end and period.end > span.start
        ]
        for i in inside:
            if self._periods[i].start < span.start or self._periods[i].end > span.end:
                raise ValueError("trim crosses a Period; choose whole Periods")
        if not inside:
            return self._slice(0, 0)
        return self._slice(inside[0], inside[-1] + 1)

    def extend(self, *, count: int) -> Periods:
        """Return these Periods with ``count`` more steps at the end."""
        if type(count) is not int or count < 0:
            raise ValueError("count must be a nonnegative integer")
        if self._periods and self._periods[-1].end != self._step(len(self)):
            raise ValueError("cannot extend Periods that end with a partial Period")
        total = len(self) + count
        periods = tuple(
            make_period(self._step(i), self._step(i + 1)) for i in range(total)
        )
        return Periods._of(
            periods,
            frequency=self._frequency,
            month_roll=self._month_roll,
            anchor=self._anchor,
            first=self._first,
        )

    def containing(self, *, on: date) -> Period:
        """Return the Period that contains a date; a date outside raises."""
        require_date(on)
        for period in self._periods:
            if period.start <= on < period.end:
                return period
        raise MissingReferenceError(
            on.isoformat(), kind="Period", by="date", where=repr(self)
        )


def make_period(start: date, end: date) -> Period:
    """Construct a positive interval; convert old inclusive end dates explicitly."""
    return Period(
        start=require_date(start),
        end=require_date(end),
    )


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
    return tuple(make_period(a, b) for a, b in pairwise(boundaries))


def periods_between(
    start: date,
    end: date,
    *,
    frequency: Frequency,
    include_partial: bool = False,
    month_roll: MonthRoll = MonthRoll.PRESERVE_END,
) -> tuple[Period, ...]:
    """Partition an interval; require explicit permission for a partial final period."""
    if elapsed_days(start, end) < 0:
        raise ValueError("end precedes start")
    offset(start, frequency=frequency, count=0, month_roll=month_roll)
    if type(include_partial) is not bool:
        raise TypeError("include_partial must be a Boolean")
    count = count_steps(start, end, frequency=frequency, month_roll=month_roll)
    result = make_periods(
        start, frequency=frequency, count=count, month_roll=month_roll
    )
    previous = result[-1].end if result else start
    if previous < end:
        if not include_partial:
            raise ValueError("span contains a partial final period")
        result += (make_period(previous, end),)
    return result


def containing_period(
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
    return Span(
        start=min(p.start for p in periods),
        end=max(p.end for p in periods),
        name=name,
    )
