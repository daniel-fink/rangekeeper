"""Present value, NPV, IRR and loan payments on known amounts, with units.

Rates are effective rates per year, such as ``"7 % pa"``, as Quantities or
their text. Each amount is discounted from its date: the recorded date of a
Movement, or else its Period's date by ``timing`` (by default the end of the
Period). The year fraction between two dates uses ``day_count``, by default
actual/actual (ISDA), so a calendar year is exactly one year. PyXIRR finds IRR
roots; ``npv`` and ``pv`` use the same discounting, so a price equal to the
NPV earns the discount rate.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from uuid import uuid4

from rangekeeper.duration.calendar import DayCount, Frequency, require_date
from rangekeeper.duration.period import PeriodTiming, steps
from rangekeeper.flow import Flow
from rangekeeper.money import is_currency
from rangekeeper.quantity import Quantity, default_units
from rangekeeper.schema import records
from rangekeeper.shared.errors import ContractError, NumericalError, UnitError
from rangekeeper.shared.optional import requires

# The unit of one step of each Frequency that a payment can be per.
_PER = {
    Frequency.DAY: "day",
    Frequency.WEEK: "week",
    Frequency.MONTH: "month",
    Frequency.QUARTER: "quarter",
    Frequency.YEAR: "year",
}


def _quantity(value: Quantity | str, name: str) -> Quantity:
    quantity = Quantity(text=value) if isinstance(value, str) else value
    if not isinstance(quantity, records.Quantity):
        raise TypeError(f"{name} must be a Quantity or its text")
    return quantity


def _rate(rate: Quantity | str) -> float:
    """Return an effective rate per year, such as ``"7 % pa"``, as a number."""
    value = default_units.convert(_quantity(rate, "rate"), to="pa").number
    if not math.isfinite(value) or value <= -1:
        raise ContractError(
            "rate must be finite and greater than -100 % pa", values={"rate": value}
        )
    return value


def _dates(flow: Flow, timing: PeriodTiming) -> list[date]:
    if not isinstance(flow, Flow):
        raise TypeError("flow must be a Flow")
    if not isinstance(timing, PeriodTiming):
        raise TypeError("timing must be a PeriodTiming")
    flow.require_resolved()
    return [movement.resolve(timing=timing) for movement in flow.movements]


def _discounted(
    flow: Flow,
    *,
    rate: float,
    on: date,
    day_count: DayCount,
    timing: PeriodTiming,
) -> list[float]:
    """Return each amount discounted to ``on``: amount / (1 + rate) ** years."""
    with requires("calculations"):
        import pyxirr  # noqa: PLC0415 - optional dependency

    from rangekeeper.finance.financial import resolve_day_count  # noqa: PLC0415 - the package loads financial on first use

    convention = resolve_day_count(day_count)
    require_date(on)
    values = [
        movement.number / (1 + rate) ** pyxirr.year_fraction(on, day, convention)
        for movement, day in zip(flow.movements, _dates(flow, timing), strict=True)
    ]
    if any(not math.isfinite(value) for value in values):
        raise NumericalError("discounting produced a non-finite amount")
    return values


def pv(
    *,
    flow: Flow,
    rate: Quantity | str,
    on: date,
    day_count: DayCount = DayCount.ACTUAL_ACTUAL,
    timing: PeriodTiming = PeriodTiming.END,
) -> Flow:
    """Return the present value on ``on`` of each amount, on the same coordinates.

    Each amount is divided by ``(1 + rate) ** t``, where ``t`` is the years from
    ``on`` to its date. An amount before ``on`` grows instead.
    """
    values = _discounted(
        flow, rate=_rate(rate), on=on, day_count=day_count, timing=timing
    )
    return flow.replace(
        movements=tuple(
            movement.replace(id=uuid4(), magnitude=value)
            for movement, value in zip(flow.movements, values, strict=True)
        )
    )


def npv(
    *,
    flow: Flow,
    rate: Quantity | str,
    on: date,
    day_count: DayCount = DayCount.ACTUAL_ACTUAL,
    timing: PeriodTiming = PeriodTiming.END,
) -> Quantity:
    """Return the net present value on ``on``: the total of ``pv``.

    An empty Flow has zero value.
    """
    total = pv(flow=flow, rate=rate, on=on, day_count=day_count, timing=timing).total()
    assert total is not None
    return total


def irr(
    *,
    flow: Flow,
    guess: Quantity | str | None = None,
    day_count: DayCount = DayCount.ACTUAL_ACTUAL,
    timing: PeriodTiming = PeriodTiming.END,
) -> Quantity:
    """Return the internal rate of return, in ``% pa``: the rate whose NPV is zero.

    The amounts need both signs and at least two dates. PyXIRR finds one root;
    a ``guess`` is a starting point, not a bound, and several roots can exist.
    The NPV at the root, on the first date, must be at most 1e-8 of the
    gross amounts.
    """
    with requires("calculations"):
        import pyxirr  # noqa: PLC0415 - optional dependency

    from rangekeeper.finance.financial import resolve_day_count  # noqa: PLC0415 - the package loads financial on first use

    dates = _dates(flow, timing)
    amounts = [movement.number for movement in flow.movements]
    if not any(a < 0 for a in amounts) or not any(a > 0 for a in amounts):
        raise NumericalError("IRR needs both positive and negative amounts")
    if len(set(dates)) < 2:
        raise NumericalError("IRR needs amounts on at least two dates")
    start = None if guess is None else _rate(guess)
    root = pyxirr.xirr(
        dates, amounts, guess=start, day_count=resolve_day_count(day_count)
    )
    if root is None or not math.isfinite(root) or root <= -1:
        raise NumericalError("IRR did not produce a finite rate above -100 % pa")
    residual = math.fsum(
        _discounted(flow, rate=root, on=min(dates), day_count=day_count, timing=timing)
    )
    if abs(residual) > 1e-8 * max(1.0, math.fsum(abs(a) for a in amounts)):
        raise NumericalError("IRR residual exceeds the acceptance tolerance")
    return Quantity(magnitude=100 * root, units="% pa")


def payment(
    *,
    principal: Quantity | str,
    rate: Quantity | str,
    term: Quantity | str,
    frequency: Frequency,
) -> Quantity:
    """Return the level payment per period that repays a loan, like a spreadsheet's PMT.

    ``rate`` is a nominal rate per year, divided equally over the periods of
    one year: ``"6 % pa"`` monthly is 0.5 % a month. ``term`` is a whole number
    of periods, such as ``"20 years"``. The payment is paid at the end of each
    period, has the sign of the principal, and is per period: ``AUD per month``.
    """
    amount = _quantity(principal, "principal")
    if not is_currency(amount.units):
        raise UnitError(f"principal must be a currency amount, not {amount.units!r}")
    if frequency not in _PER:
        raise ContractError(
            f"payments per {frequency.value} have no unit; use day, week, month, "
            "quarter or year",
            values={"frequency": frequency.value},
        )
    count = _periods(term, frequency)
    days, months = frequency.step
    per_period = _rate(rate) * (months / 12 if months else days / 365.25)
    value = (
        amount.number / count
        if per_period == 0
        else amount.number * per_period / (1 - (1 + per_period) ** -count)
    )
    if not math.isfinite(value):
        raise NumericalError("payment produced a non-finite amount")
    return Quantity(magnitude=value, units=f"{amount.units} per {_PER[frequency]}")


def _periods(term: Quantity | str, frequency: Frequency) -> int:
    """Return the whole number of ``frequency`` periods in a term."""
    unit, count = steps(_quantity(term, "term"))
    (days, months), (step_days, step_months) = unit.step, frequency.step
    if bool(months) != bool(step_months):
        raise UnitError("give the term in the same kind of calendar unit as frequency")
    length, step = (months, step_months) if months else (days, step_days)
    if (count * length) % step:
        raise UnitError(f"the term is not a whole number of {frequency.value} periods")
    return count * length // step


__all__: Sequence[str] = ("irr", "npv", "payment", "pv")
