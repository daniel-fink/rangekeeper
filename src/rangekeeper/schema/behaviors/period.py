"""Date-only interval behaviour shared by Period and its schema subclasses."""

from __future__ import annotations
from datetime import date, timedelta
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from rangekeeper.schema.records import Period
    from rangekeeper.model.duration.calendar import PeriodTiming


class PeriodBehavior:
    """Interpret half-open boundaries without storing derived dates."""

    __slots__ = ()

    @property
    def first(self) -> date:
        return cast("Period", self).start_inclusive

    @property
    def last(self) -> date:
        return cast("Period", self).end_exclusive - timedelta(days=1)

    @property
    def end(self) -> date:
        return cast("Period", self).end_exclusive

    def check(self) -> Period:
        """Require a positive date interval [start_inclusive, end_exclusive)."""
        period = cast("Period", self)
        from rangekeeper.model.duration.calendar import elapsed_days

        if elapsed_days(period.start_inclusive, period.end_exclusive) <= 0:
            raise ValueError("period end must follow start")
        return period

    def resolve(self, *, timing: PeriodTiming) -> date:
        """Select the first included date, last included date or excluded boundary."""
        from rangekeeper.model.duration.calendar import PeriodTiming

        if not isinstance(timing, PeriodTiming):
            raise TypeError("timing must be a PeriodTiming")
        period = cast("Period", self)
        period.check()
        return {
            PeriodTiming.FIRST: period.first,
            PeriodTiming.LAST: period.last,
            PeriodTiming.END: period.end,
        }[timing]
