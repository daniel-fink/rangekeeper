"""Date values: a calendar date, or NEVER when the event does not happen.

``NEVER`` is the one member of a one-member enum. It is a result, not a missing
value: ``None`` means missing. NEVER equals NEVER and is later than every date,
so a bound such as ``b_start >= shared_start + 1 year`` holds when Building B
never starts.
"""

from __future__ import annotations

from datetime import date
from typing import TypeAlias

from rangekeeper.duration.calendar import offset, require_date
from rangekeeper.duration.period import signed_steps
from rangekeeper.quantity import Quantity
from rangekeeper.schema.enums import Never

NEVER = Never.NEVER
"""The event does not happen. It is not ``None``, which means missing."""

DateValue: TypeAlias = date | Never
"""The content of a date Value: a calendar date or ``NEVER``."""


def require_date_value(value: object) -> DateValue:
    """Require a calendar date or NEVER; never truncate a datetime."""
    if value is NEVER:
        return NEVER
    if not isinstance(value, date):
        raise TypeError("a date value must be a calendar date or rk.duration.NEVER")
    return require_date(value)


def shift(on: DateValue, *, by: Quantity | str) -> DateValue:
    """Return the date a whole length later, such as ``"1 year"``, or earlier.

    ``by`` is a whole number of days, weeks, months, quarters or years, as a
    Quantity or its text; a negative length gives an earlier date. A month step
    keeps the last day of a month. NEVER shifted by any length is NEVER.
    """
    value = require_date_value(on)
    frequency, count = signed_steps(by)
    if value is NEVER:
        return NEVER
    assert isinstance(value, date)
    return offset(value, frequency=frequency, count=count)


def order(value: DateValue) -> tuple[int, date]:
    """Return a sort key that puts NEVER after every date."""
    if require_date_value(value) is NEVER:
        return (1, date.max)
    assert isinstance(value, date)
    return (0, value)


__all__ = ["NEVER", "DateValue", "Never", "order", "require_date_value", "shift"]
