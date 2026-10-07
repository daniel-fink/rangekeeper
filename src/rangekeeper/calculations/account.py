"""Account recurrence with explicit bases, current interest and charge treatment."""

from __future__ import annotations

from uuid import uuid4
from dataclasses import dataclass
import math

from ..account import Balance, CurrentInterest, InterestTreatment, check_conventions
from .._coordinates import index
from ..model.flow import Flow
from ..model.measure import Quantity
from ..units import default_units


def _check_rate(rate: float, current_interest: CurrentInterest) -> float:
    if (
        type(rate) not in (int, float)
        or not math.isfinite(rate)
        or rate <= -1
        or current_interest is CurrentInterest.INCLUDED
        and rate >= 1
    ):
        raise ValueError("invalid per-period interest rate")
    return float(rate)


@dataclass(frozen=True, slots=True)
class Account:
    """Opening, closing, overdraft and interest Flows from one signed recurrence."""

    opening: Flow
    closing: Flow
    overdraft: Flow
    overdraft_balance: Flow
    interest: Flow

    def difference(self) -> Flow:
        """Change in nonnegative balance, excluding the separate overdraft."""
        return self.closing.replace(
            movements=tuple(
                c.replace(id=uuid4(), magnitude=c.number - o.number)
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
        balance: Balance = Balance.CLOSING,
        current_interest: CurrentInterest = CurrentInterest.EXCLUDED,
        treatment: InterestTreatment = InterestTreatment.SEPARATE,
    ) -> Account:
        """Apply principal transactions and a per-step rate in original Flow order.

        OPENING selects debt before transactions; CLOSING selects debt after them.
        INCLUDED solves I = r * (base + I) and requires FINANCED treatment.
        A nonpositive base earns zero interest. Display balances are clamped;
        the recurrence retains signed balances and separate overdraft changes.
        """
        check_conventions(
            balance=balance, current_interest=current_interest, treatment=treatment
        )
        transactions.check(resolved=True)
        coordinates = index(transactions.movements)
        running = default_units.convert(starting, to=transactions.units).magnitude
        if not math.isfinite(running):
            raise ValueError("starting balance must be finite")
        if isinstance(rate, Flow):
            rate.check(resolved=True)
            rates = index(rate.convert(units="dimensionless").movements)
            if tuple(rates) != tuple(coordinates):
                raise ValueError(
                    "Flow coordinates differ; rate order must match transactions"
                )
            prepared_rates = {
                key: _check_rate(movement.number, current_interest)
                for key, movement in rates.items()
            }
            scalar_rate = None
        else:
            scalar_rate = _check_rate(rate, current_interest)
            prepared_rates = {}
        opens, closes, deficits, interests = [], [], [], []
        for movement in transactions.movements:
            period_rate = (
                scalar_rate
                if scalar_rate is not None
                else prepared_rates[movement.coordinate]
            )
            before_interest = running + movement.number
            selected = running if balance is Balance.OPENING else before_interest
            charge = max(selected, 0) * period_rate
            if current_interest is CurrentInterest.INCLUDED:
                charge /= 1 - period_rate
            # Retain the characterized ordering for opening-base financed charges.
            if treatment is InterestTreatment.FINANCED and balance is Balance.OPENING:
                closing = (running + charge) + movement.number
            else:
                closing = (
                    before_interest + charge
                    if treatment is InterestTreatment.FINANCED
                    else before_interest
                )
            if not all(
                math.isfinite(value) for value in (before_interest, charge, closing)
            ):
                raise ValueError("account recurrence produced a nonfinite result")
            opens.append(movement.replace(id=uuid4(), magnitude=max(running, 0)))
            closes.append(movement.replace(id=uuid4(), magnitude=max(closing, 0)))
            deficits.append(movement.replace(id=uuid4(), magnitude=min(closing, 0)))
            interests.append(movement.replace(id=uuid4(), magnitude=charge))
            running = closing
        deficit_flow = transactions.replace(movements=tuple(deficits)).check()
        return cls(
            transactions.replace(movements=tuple(opens)).check(),
            transactions.replace(movements=tuple(closes)).check(),
            deficit_flow.difference(initial=0),
            deficit_flow,
            transactions.replace(movements=tuple(interests)).check(),
        )
