"""Present value, NPV, IRR, interest and loan payments on known amounts, with units.

Rates are effective rates per year, such as ``"7 % pa"``, as Quantities or
their text. Each amount is discounted from its date: the recorded date of a
Movement, or else its Period's date by ``timing`` (by default the end of the
Period). The year fraction between two dates uses ``day_count``, by default
actual/actual (ISDA), so a calendar year is exactly one year. PyXIRR finds IRR
roots; ``npv`` and ``pv`` use the same discounting, so a price equal to the
NPV earns the discount rate. ``check_sign_change`` is for internal use: the
solve applies it to a Flow whose IRR an equation fixes.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from uuid import uuid4

from rangekeeper.duration.calendar import (
    DayCount,
    Frequency,
    require_date,
    year_fraction,
)
from rangekeeper.duration.period import PeriodTiming, steps
from rangekeeper.flow import Flow
from rangekeeper.money import is_currency
from rangekeeper.quantity import Quantity, default_units
from rangekeeper.schema import records
from rangekeeper.shared.codes import Code
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
    value = default_units.convert(quantity=_quantity(rate, "rate"), to="pa").number
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

    The amounts need inflows and outflows, on at least two dates. An amount
    within the acceptance tolerance, 1e-8 of the gross amounts (at least
    1e-8 of one unit), counts as zero: amounts without a real change of sign,
    such as an equity cash flow whose only inflows are rounding noise, raise
    NumericalError with the code ``no_sign_change``. PyXIRR finds one root;
    a ``guess`` is a starting point, not a bound, and several roots can
    exist. The NPV at the root, on the first date, must be within the same
    tolerance.
    """
    with requires("calculations"):
        import pyxirr  # noqa: PLC0415 - optional dependency

    from rangekeeper.finance.financial import resolve_day_count  # noqa: PLC0415 - the package loads financial on first use

    dates = _dates(flow, timing)
    check_sign_change(flow)
    amounts = [movement.number for movement in flow.movements]
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
    if abs(residual) > _tolerance(amounts):
        raise NumericalError("IRR residual exceeds the acceptance tolerance")
    return Quantity(magnitude=100 * root, units="% pa")


def _tolerance(amounts: Sequence[float]) -> float:
    """Return the acceptance tolerance of an IRR: 1e-8 of the gross amounts.

    The tolerance is at least 1e-8 of one unit. It bounds the NPV at the root,
    and an amount within it counts as zero.
    """
    return 1e-8 * max(1.0, math.fsum(abs(a) for a in amounts))


def check_sign_change(flow: Flow) -> None:
    """Raise NumericalError unless an inflow and an outflow exceed the tolerance.

    The error has the code ``no_sign_change``, and its message and ``values``
    give the totals of the inflows and of the outflows, and the tolerance.
    ``irr`` calls this function; the solve calls it for a fixed IRR.
    """
    amounts = [movement.number for movement in flow.movements]
    tolerance = _tolerance(amounts)
    if any(a > tolerance for a in amounts) and any(a < -tolerance for a in amounts):
        return
    values = {
        name: str(Quantity(magnitude=amount, units=flow.units))
        for name, amount in (
            ("inflows", math.fsum(a for a in amounts if a > 0)),
            ("outflows", math.fsum(a for a in amounts if a < 0)),
            ("tolerance", tolerance),
        )
    }
    raise NumericalError(
        f"IRR needs inflows and outflows: the inflows total {values['inflows']} and"
        f" the outflows total {values['outflows']}. An amount within"
        f" {values['tolerance']}, 1e-8 of the gross amounts, counts as zero.",
        code=Code.NO_SIGN_CHANGE,
        values=values,
    )


def interest(
    *,
    balance: Flow,
    rate: Quantity | str,
    day_count: DayCount = DayCount.ACTUAL_ACTUAL,
) -> Flow:
    """Return the interest on a balance in each Period, on the same Periods.

    The balance of each Period earns interest over that Period at an effective
    rate per year, as ``pv`` and ``npv`` discount: ``balance * ((1 + rate) **
    t - 1)``, where ``t`` is the Period's length in years by ``day_count``. A
    yearly Period at ``"6 % pa"`` earns 6 % of its balance. The interest has
    the units and the sign of the balance. A dated Movement has no length,
    so a Flow over dates raises ContractError; an unresolved balance raises
    NumericalError.
    """
    if not isinstance(balance, Flow):
        raise TypeError("balance must be a Flow")
    if not isinstance(day_count, DayCount):
        raise TypeError("day_count must be a DayCount")
    periods = [movement.period for movement in balance.movements]
    if any(period is None for period in periods):
        raise ContractError("interest needs a balance over Periods, not over dates")
    balance.require_resolved()
    effective = _rate(rate)
    values = [
        movement.number
        * ((1 + effective) ** year_fraction(p.start, p.end, convention=day_count) - 1)
        for movement, p in zip(balance.movements, periods, strict=True)
        if p is not None
    ]
    if any(not math.isfinite(value) for value in values):
        raise NumericalError("interest produced a non-finite amount")
    return Flow.from_periods(
        periods=[p for p in periods if p is not None],
        magnitudes=values,
        units=balance.units,
    )


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


__all__: Sequence[str] = ("check_sign_change", "irr", "npv", "payment", "pv")
