"""PyXIRR financial calculations with RK dates, units and immutable results.

RK resolves period timing and checks inputs/results. PyXIRR owns discounting,
day-count arithmetic and root finding; no second financial solver is maintained.
Calling these operations treats the supplied entries as dated amounts. The model
is responsible for that interpretation; Flow records carry no semantic kinds.
"""

from __future__ import annotations

from uuid import uuid4

from dataclasses import dataclass
from datetime import date
import math

from ..model.flow import Flow
from ..model.measure import Quantity
from ..duration.period import PeriodTiming
from ..duration.calendar import DayCount, require_date, resolve_day_count


def _require_result(value: float | None, operation: str) -> float:
    """Turn absent/nonfinite backend results into an explicit calculation failure."""
    if value is None or not math.isfinite(value):
        raise ValueError(f"{operation} did not produce a finite result")
    return value


def calculate_pv(flow: Flow, *, rate: float, first_period: int = 1) -> Flow:
    """Discount each movement with PyXIRR PV, retaining its coordinates and Claims.

    Rate is per movement period; first_period=1 places the first payment one period
    after valuation. No date convention is inferred from period coverage.
    """
    import pyxirr

    flow.check(resolved=True)
    if not math.isfinite(rate) or rate <= -1 or type(first_period) is not int:
        raise ValueError("rate must exceed -1 and first_period must be an integer")
    return flow.replace(
        movements=tuple(
            movement.replace(
                id=uuid4(),
                magnitude=_require_result(
                    pyxirr.pv(rate, first_period + i, 0, -movement.number), "PV"
                ),
            )
            for i, movement in enumerate(flow.movements)
        )
    ).check()


def calculate_xnpv(
    flow: Flow,
    *,
    rate: float,
    valuation_date: date,
    day_count: DayCount = DayCount.ACTUAL_365,
    timing: PeriodTiming | None = None,
) -> Quantity:
    """Use PyXIRR XNPV and PV to value movements on an explicit date.

    PyXIRR anchors XNPV at the earliest payment. PV moves that result to the
    requested valuation date, before or after payment, under the same day count.
    Undated period movements require timing; recorded dates take precedence.
    Empty Flows have zero value and never enter PyXIRR's empty-date path.
    """
    import pyxirr

    flow.check(resolved=True)
    if timing is not None and not isinstance(timing, PeriodTiming):
        raise TypeError("timing must be a PeriodTiming")
    require_date(valuation_date)
    if not math.isfinite(rate) or rate <= -1:
        raise ValueError("rate must be finite and greater than -1")
    convention = resolve_day_count(day_count)
    if not flow.movements:
        return Quantity(magnitude=0, units=flow.units)
    dates = [movement.resolve(timing=timing) for movement in flow.movements]
    amounts = [movement.number for movement in flow.movements]
    value = _require_result(
        pyxirr.xnpv(rate, dates, amounts, day_count=convention), "XNPV"
    )
    periods = pyxirr.year_fraction(valuation_date, min(dates), convention)
    value = _require_result(pyxirr.pv(rate, periods, 0, -value), "XNPV valuation")
    return Quantity(magnitude=value, units=flow.units)


@dataclass(frozen=True, slots=True)
class IrrResult:
    """One PyXIRR result and its NPV residual; does not establish root uniqueness."""

    rate: float
    residual: Quantity
    guess: float | None
    method: str = "pyxirr.xirr"


def calculate_irr(
    flow: Flow,
    *,
    guess: float | None = None,
    valuation_date: date | None = None,
    day_count: DayCount = DayCount.ACTUAL_365,
    timing: PeriodTiming | None = None,
) -> IrrResult:
    """Find one dated IRR through PyXIRR, optionally supplying an initial guess.

    The library selects the root; a guess is not a search bound or a guarantee of
    the nearest root. Multiple roots can exist. Reject absent/nonfinite results
    and residuals above 1e-8 of gross movements (with a one-unit scale floor).
    Same-day payments cannot determine an IRR. Undated periods require timing.
    valuation_date controls residual reporting; it does not change the solver.
    """
    import pyxirr

    flow.check(resolved=True)
    if timing is not None and not isinstance(timing, PeriodTiming):
        raise TypeError("timing must be a PeriodTiming")
    if guess is not None and (not math.isfinite(guess) or guess <= -1):
        raise ValueError("IRR guess must be finite and greater than -1")
    if valuation_date is not None:
        require_date(valuation_date)
    convention = resolve_day_count(day_count)
    dates = [movement.resolve(timing=timing) for movement in flow.movements]
    amounts = [movement.number for movement in flow.movements]
    if not any(amount < 0 for amount in amounts) or not any(
        amount > 0 for amount in amounts
    ):
        raise ValueError("IRR requires both positive and negative movements")
    if len(set(dates)) < 2:
        raise ValueError("IRR requires payments on distinct dates")
    root = _require_result(
        pyxirr.xirr(dates, amounts, guess=guess, day_count=convention), "IRR"
    )
    if root <= -1:
        raise ValueError("IRR must be greater than -1")
    residual = calculate_xnpv(
        flow,
        rate=root,
        valuation_date=valuation_date or min(dates),
        day_count=day_count,
        timing=timing,
    )
    if abs(residual.magnitude) > 1e-8 * max(
        1.0, math.fsum(abs(amount) for amount in amounts)
    ):
        raise ValueError("IRR residual exceeds acceptance tolerance")
    return IrrResult(root, residual, guess)
