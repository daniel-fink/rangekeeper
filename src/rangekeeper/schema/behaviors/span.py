"""Calendar convenience for named extents, without an owned frequency."""

from __future__ import annotations
from datetime import date
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from rangekeeper.schema.records import Span, Period
    from rangekeeper.model.duration.calendar import Frequency, MonthRoll


class SpanBehavior:
    __slots__ = ()

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
        from rangekeeper.model.duration.calendar import offset, MonthRoll

        if type(count) is not int or count <= 0:
            raise ValueError("span count must be a positive integer")
        factory = cast("type[Span]", cls)
        span = factory(
            name=name,
            start_inclusive=start,
            end_exclusive=offset(
                start,
                frequency=frequency,
                count=count,
                month_roll=MonthRoll.PRESERVE_END if month_roll is None else month_roll,
            ),
        )
        span.check()
        return span

    def periods(
        self,
        frequency: Frequency,
        *,
        include_partial: bool = False,
        month_roll: MonthRoll | None = None,
    ) -> tuple[Period, ...]:
        """Partition this extent; a partial final period requires explicit permission."""
        from rangekeeper.model.duration.period import periods_between
        from rangekeeper.model.duration.calendar import MonthRoll

        span = cast("Span", self)
        span.check()
        return periods_between(
            span.start_inclusive,
            span.end_exclusive,
            frequency=frequency,
            include_partial=include_partial,
            month_roll=MonthRoll.PRESERVE_END if month_roll is None else month_roll,
        )
