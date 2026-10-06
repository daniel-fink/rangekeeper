"""Account recurrence preserving explicit interest timing and overdraft movements."""

from __future__ import annotations

from dataclasses import dataclass
import math

from ..model.flow import Flow
from ..model.measure import Quantity
from ..units import default_units
from .series import align


@dataclass(frozen=True, slots=True)
class Account:
    """Opening, closing and interest Flows from one explicit account recurrence."""

    opening: Flow
    closing: Flow
    overdraft: Flow
    overdraft_balance: Flow
    interest: Flow

    def difference(self) -> Flow:
        """Change in nonnegative account balance, excluding the separate overdraft."""
        return self.closing.replace(
            movements=tuple(
                c.replace(magnitude=c.number - o.number)
                for o, c in zip(self.opening.movements, self.closing.movements)
            )
        ).check()

    @classmethod
    def calculate(
        cls,
        transactions: Flow,
        *,
        starting: Quantity,
        rate: float | Flow = 0,
        method: str = "simple",
        timing: str = "advance",
    ) -> Account:
        """Calculate simple, compound or capitalized interest on positive principal.

        Advance transactions enter before interest; arrears enter after interest.
        Negative principal is tracked separately as an overdraft balance. The overdraft
        movement is its period change, including any negative initial balance at time 0,
        matching the legacy consumer convention. rate supplies per-period interest as
        a scalar ratio or an aligned dimensionless Flow (percent units are converted).
        The caller assigns these roles; the input Flows carry no semantic kinds.
        No input is mutated.
        """
        transactions.check(resolved=True)
        if method not in {"simple", "compound", "capitalized"} or timing not in {
            "advance",
            "arrears",
        }:
            raise ValueError("invalid interest method or transaction timing")
        opening_value = default_units.convert(starting, to=transactions.units).magnitude
        if isinstance(rate, Flow):
            rates = [
                s.number
                for s in align((transactions, rate.convert(units="dimensionless")))
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
        for movement, period_rate in zip(transactions.movements, rates):
            opening = max(opening_value, 0)
            principal = opening_value + (movement.number if timing == "advance" else 0)
            interest = max(principal, 0) * period_rate
            if method == "capitalized":
                interest /= 1 - period_rate
            if method != "simple":
                principal += interest
            if timing == "arrears":
                principal += movement.number
            opens.append(movement.replace(magnitude=opening))
            closes.append(movement.replace(magnitude=max(principal, 0)))
            deficits.append(movement.replace(magnitude=min(principal, 0)))
            interests.append(movement.replace(magnitude=interest))
            opening_value = principal
        deficit_flow = transactions.replace(movements=tuple(deficits)).check()
        return cls(
            transactions.replace(movements=tuple(opens)).check(),
            transactions.replace(movements=tuple(closes)).check(),
            deficit_flow.difference(initial=0),
            deficit_flow,
            transactions.replace(movements=tuple(interests)).check(),
        )
