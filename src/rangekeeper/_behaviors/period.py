"""Date-only interval behaviour, shared by Period and its schema subclasses."""

from __future__ import annotations
from datetime import date, timedelta
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .._schema.records import Period
    from ..duration.period import PeriodTiming


class PeriodBehavior:
    """Interpret half-open boundaries without storing derived dates."""

    __slots__ = ()

    def check(self) -> Period:
        """Require a positive date interval [start, end)."""
        period = cast("Period", self)
        from ..duration.calendar import elapsed_days

        if elapsed_days(period.start, period.end) <= 0:
            raise ValueError("period end must follow start")
        return period

    def resolve(self, *, timing: PeriodTiming) -> date:
        """Derive a date without storing a duplicate field.

        start is the first included day; last_day is the final included day; end is
        the exclusive boundary (for example, payment on the next month's first day).
        """
        period = cast("Period", self)
        period.check()
        if timing == "start":
            return period.start
        if timing == "last_day":
            return period.end - timedelta(days=1)
        if timing == "end":
            return period.end
        raise ValueError("timing must be start, last_day or end")
