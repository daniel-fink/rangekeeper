"""Migrated known-data development account example, independent of legacy modules."""

from dataclasses import dataclass
from datetime import date

from rangekeeper.calculations import account, projection, series
from rangekeeper.calculations.account import Account, CurrentInterest, InterestTreatment
from rangekeeper.model.duration import Frequency, make_periods
from rangekeeper.model.flux import Flow, MissingValueHandling
from rangekeeper.model.measure import Quantity


@dataclass(frozen=True)
class DevelopmentAccounts:
    draws: Flow
    payments: Flow
    equity: account.Account
    loan: account.Account


def build_accounts(
    *,
    acquisition=0.0,
    equity=0.0,
    costs=500000.0,
    payments=1000000.0,
    interest_rate=0.05,
    starting=date(2020, 1, 1),
) -> DevelopmentAccounts:
    """Nine monthly draws, three repayments; advance transactions and capitalized debt."""
    periods = make_periods(starting, frequency=Frequency.MONTH, count=12)
    purchase = projection.distribute(
        Quantity(magnitude=-acquisition, units="AUD"), periods=periods[:1]
    )
    construction = projection.distribute(
        Quantity(magnitude=-costs, units="AUD"), periods=periods[:9]
    )
    draws = series.aggregate(
        (purchase, construction),
        join=series.AlignmentJoin.UNION,
        missing=MissingValueHandling.ZERO,
    ).flow
    receipts = projection.distribute(
        Quantity(magnitude=payments, units="AUD"), periods=periods[9:]
    )
    equity_account = Account.calculate(
        draws, starting=Quantity(magnitude=equity, units="AUD")
    )
    debt = series.aggregate(
        (equity_account.overdraft.negate(), receipts.negate()),
        join=series.AlignmentJoin.UNION,
        missing=MissingValueHandling.ZERO,
    ).flow
    loan = Account.calculate(
        debt,
        starting=Quantity(magnitude=0, units="AUD"),
        rate=interest_rate / 12,
        current_interest=CurrentInterest.INCLUDED,
        treatment=InterestTreatment.FINANCED,
    )
    return DevelopmentAccounts(draws, receipts, equity_account, loan)
