"""Account recurrence preserving explicit interest timing and overdraft movements."""

from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Sequence

from ..model.flow import Flow
from ..model.measure import Quantity
from ..units import default_units
from .series import align, convert, difference
from ._flow import replace_movement, replace_movements, require_resolved, magnitude


@dataclass(frozen=True, slots=True)
class AccountResult:
    opening: Flow
    closing: Flow
    overdraft: Flow
    overdraft_balance: Flow
    interest: Flow

    def difference(self) -> Flow:
        """Change in nonnegative account balance, excluding the separate overdraft."""
        return replace_movements(
            self.closing,
            [
                replace_movement(c, magnitude(c) - magnitude(o))
                for o, c in zip(self.opening.movements, self.closing.movements)
            ],
        )


def calculate_account(
    transactions: Flow,
    *,
    starting: Quantity,
    rate: float | Flow = 0,
    method: str = "simple",
    timing: str = "advance",
) -> AccountResult:
    """Calculate simple, compound or capitalized interest on positive principal.

    Advance transactions enter before interest; arrears enter after interest.
    Negative principal is tracked separately as an overdraft balance. The overdraft
    movement is its period change, including any negative initial balance at time 0,
    matching the legacy consumer convention. rate supplies per-period interest as
    a scalar ratio or an aligned dimensionless Flow (percent units are converted).
    The caller assigns these roles; the input Flows carry no semantic kinds.
    No input is mutated.
    """
    require_resolved(transactions)
    if method not in {"simple", "compound", "capitalized"} or timing not in {
        "advance",
        "arrears",
    }:
        raise ValueError("invalid interest method or transaction timing")
    opening_value = default_units.convert(starting, to=transactions.units).magnitude
    if isinstance(rate, Flow):
        rates = [
            magnitude(s)
            for s in align((transactions, convert(rate, units="dimensionless")))
            .flows[1]
            .movements
        ]
    else:
        rates = [rate] * len(transactions.movements)
    if any(
        type(r) not in (int, float)
        or not math.isfinite(r)
        or r <= -1
        or method == "capitalized"
        and r >= 1
        for r in rates
    ):
        raise ValueError("invalid per-period interest rate")
    opens, closes, deficits, interests = [], [], [], []
    previous_deficit = 0.0
    for movement, period_rate in zip(transactions.movements, rates):
        opening = max(opening_value, 0)
        principal = opening_value + (magnitude(movement) if timing == "advance" else 0)
        interest = max(principal, 0) * period_rate
        if method == "capitalized":
            interest /= 1 - period_rate
        if method != "simple":
            principal += interest
        if timing == "arrears":
            principal += magnitude(movement)
        opens.append(replace_movement(movement, opening))
        closes.append(replace_movement(movement, max(principal, 0)))
        deficits.append(replace_movement(movement, min(principal, 0)))
        interests.append(replace_movement(movement, interest))
        opening_value = principal
    deficit_flow = replace_movements(transactions, deficits)
    return AccountResult(
        replace_movements(transactions, opens),
        replace_movements(transactions, closes),
        difference(deficit_flow, initial=0),
        deficit_flow,
        replace_movements(transactions, interests),
    )
