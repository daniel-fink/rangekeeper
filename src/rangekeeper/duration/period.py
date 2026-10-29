"""Period, Span and Periods: half-open periods from an anchor and a calendar step."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
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
    require_frequency,
    require_month_roll,
)
from rangekeeper.duration.calendar import PeriodTiming as PeriodTiming
from rangekeeper.duration.errors import AlignmentError
from rangekeeper.quantity import Quantity, default_units
from rangekeeper.schema import records
from rangekeeper.schema.kinds import register
from rangekeeper.schema.runtime import UNSET, Unset
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, MissingReferenceError, UnitError

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

    def periods(
        self,
        *,
        frequency: Frequency,
        include_partial: bool = False,
        month_roll: MonthRoll = MonthRoll.PRESERVE_END,
    ) -> Periods:
        """Partition this extent; a partial final period requires explicit permission."""
        if type(include_partial) is not bool:
            raise TypeError("include_partial must be a Boolean")
        steps = _Steps(anchor=self.start, frequency=frequency, month_roll=month_roll)
        count = count_steps(
            self.start, self.end, frequency=frequency, month_roll=month_roll
        )
        whole = steps.periods(0, count)
        rest = steps.boundary(count)
        if rest == self.end:
            return Periods._of(whole, steps=steps, first=0)
        if not include_partial:
            raise AlignmentError(
                f"{_interval(self)} ends with a partial {frequency.value}; "
                "pass include_partial=True to keep it",
                code=Code.ALIGNMENT_PARTIAL,
                values={
                    "span": _interval(self),
                    "frequency": frequency.value,
                    "partial": _interval(Period(start=rest, end=self.end)),
                },
            )
        return Periods._of(
            (*whole, Period(start=rest, end=self.end)), steps=steps, first=0
        )


@dataclass(frozen=True, slots=True)
class _Steps:
    """Calendar steps of one Frequency from an anchor date, by a MonthRoll."""

    anchor: date
    frequency: Frequency
    month_roll: MonthRoll

    def __post_init__(self) -> None:
        require_date(self.anchor)
        require_frequency(self.frequency)
        require_month_roll(self.month_roll)

    def boundary(self, index: int) -> date:
        """Return the date ``index`` steps from the anchor."""
        return offset(
            self.anchor,
            frequency=self.frequency,
            count=index,
            month_roll=self.month_roll,
        )

    def periods(self, start: int, stop: int) -> tuple[Period, ...]:
        """Return the Periods from step ``start`` to step ``stop``."""
        boundaries = [self.boundary(index) for index in range(start, stop + 1)]
        return tuple(Period(start=a, end=b) for a, b in pairwise(boundaries))


@dataclass(frozen=True, slots=True, init=False, eq=False, repr=False)
class Periods(Sequence[Period]):
    """An ordered, gap-free sequence of Periods with one frequency.

    ``Span.periods(frequency=)`` returns one, or make one with
    ``Periods(start=, frequency=, count=)``. Each Period is a calendar step from
    the anchor date, by ``month_roll``. Only a Span partition can end with a
    partial Period. Two Periods are equal when they have the same frequency and
    the same Periods.
    """

    _periods: tuple[Period, ...]
    _steps: _Steps
    # The step of the first Period, counted from the anchor.
    _first: int

    def __init__(
        self,
        *,
        start: date,
        frequency: Frequency,
        count: int,
        month_roll: MonthRoll = MonthRoll.PRESERVE_END,
    ) -> None:
        steps = _Steps(anchor=start, frequency=frequency, month_roll=month_roll)
        _require_count(count)
        self._assign(steps.periods(0, count), steps=steps, first=0)

    @classmethod
    def _of(cls, periods: tuple[Period, ...], *, steps: _Steps, first: int) -> Periods:
        """Return Periods from parts that the caller made from ``steps``."""
        result = object.__new__(cls)
        result._assign(periods, steps=steps, first=first)
        return result

    def _assign(
        self, periods: tuple[Period, ...], *, steps: _Steps, first: int
    ) -> None:
        object.__setattr__(self, "_periods", periods)
        object.__setattr__(self, "_steps", steps)
        object.__setattr__(self, "_first", first)

    @property
    def frequency(self) -> Frequency:
        """The calendar step of each Period."""
        return self._steps.frequency

    @property
    def start(self) -> date:
        """The start of the first Period, or the anchor of an empty sequence."""
        return self._periods[0].start if self._periods else self._boundary(0)

    @property
    def end(self) -> date:
        """The end of the last Period: the first date after the sequence."""
        return self._periods[-1].end if self._periods else self.start

    @property
    def span(self) -> Span:
        """The Span from the start to the end, without a name."""
        return Span(start=self.start, end=self.end)

    def _boundary(self, index: int) -> date:
        return self._steps.boundary(self._first + index)

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
                raise ContractError(
                    "a slice of Periods takes every Period", values={"step": step}
                )
            return self._slice(start, max(start, stop))
        return self._periods[index]

    def _slice(self, start: int, stop: int) -> Periods:
        return Periods._of(
            self._periods[start:stop], steps=self._steps, first=self._first + start
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Periods):
            return NotImplemented
        return self.frequency is other.frequency and self._periods == other._periods

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        if not self._periods:
            return f"Periods(frequency={self.frequency.value}, count=0)"
        return (
            f"Periods(start={self.start.isoformat()}, end={self.end.isoformat()}, "
            f"frequency={self.frequency.value}, count={len(self)})"
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
                raise AlignmentError(
                    f"{_interval(span)} crosses the Period "
                    f"{_interval(self._periods[i])}; choose whole Periods",
                    code=Code.ALIGNMENT_CROSSES,
                    values={
                        "span": _interval(span),
                        "period": _interval(self._periods[i]),
                    },
                )
        if not inside:
            return self._slice(0, 0)
        return self._slice(inside[0], inside[-1] + 1)

    def extend(self, *, count: int) -> Periods:
        """Return these Periods with ``count`` more steps at the end."""
        _require_count(count)
        if self._periods and self._periods[-1].end != self._boundary(len(self)):
            raise AlignmentError(
                f"{self!r} ends with a partial Period and cannot extend",
                code=Code.ALIGNMENT_PARTIAL,
                values={
                    "frequency": self.frequency.value,
                    "partial": _interval(self._periods[-1]),
                },
            )
        stop = self._first + len(self) + count
        return Periods._of(
            self._steps.periods(self._first, stop), steps=self._steps, first=self._first
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


def cover(periods: Sequence[Period], *, name: str | None = None) -> Span:
    """Return a Span covering all intervals, including gaps between them."""
    if not periods:
        raise ContractError("cover takes at least one Period", values={"count": 0})
    return Span(
        start=min(p.start for p in periods),
        end=max(p.end for p in periods),
        name=name,
    )


def _require_count(count: int) -> None:
    """Require a whole, nonnegative number of Periods."""
    if type(count) is not int:
        raise TypeError("count must be an integer")
    if count < 0:
        raise ContractError(
            f"count {count} is negative; give zero or more Periods",
            values={"count": count},
        )


def _interval(period: Period) -> str:
    """Return a Period as an ISO 8601 interval, such as ``2026-01-01/2026-02-01``."""
    return f"{period.start.isoformat()}/{period.end.isoformat()}"
