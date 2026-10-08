"""Date-only operations independent of dataframes, storage and execution."""

from rangekeeper.schema.records import Period, Span

from rangekeeper.model.duration.calendar import (
    Frequency,
    MonthRoll,
    PeriodTiming,
    DayCount,
    offset,
    measure,
    year_fraction,
)
from rangekeeper.model.duration.period import (
    make_period,
    make_periods,
    periods_between,
    align,
    cover,
)

__all__ = [
    "Frequency",
    "MonthRoll",
    "PeriodTiming",
    "DayCount",
    "offset",
    "measure",
    "year_fraction",
    "make_period",
    "make_periods",
    "periods_between",
    "align",
    "cover",
]

"""Schema-defined date intervals. Calendar operations live in ``duration``."""


__all__ += ["Period", "Span"]
