"""Migrated known-data development account example, independent of legacy modules."""

from dataclasses import dataclass
from datetime import date

from rangekeeper.duration import Frequency, make_periods
from rangekeeper.finance import account, projection
from rangekeeper.finance.account import Account, CurrentInterest, InterestTreatment
from rangekeeper.flow import AlignmentJoin, Flow, MissingValueHandling
from rangekeeper.quantity import Quantity
from tests.streams import lines


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
    draws = (
        lines((purchase, construction))
        .aggregate(join=AlignmentJoin.UNION, missing=MissingValueHandling.ZERO)
        .flow
    )
    receipts = projection.distribute(
        Quantity(magnitude=payments, units="AUD"), periods=periods[9:]
    )
    equity_account = Account.calculate(
        draws, starting=Quantity(magnitude=equity, units="AUD")
    )
    debt = (
        lines((equity_account.overdraft.negate(), receipts.negate()))
        .aggregate(join=AlignmentJoin.UNION, missing=MissingValueHandling.ZERO)
        .flow
    )
    loan = Account.calculate(
        debt,
        starting=Quantity(magnitude=0, units="AUD"),
        rate=interest_rate / 12,
        current_interest=CurrentInterest.INCLUDED,
        treatment=InterestTreatment.FINANCED,
    )
    return DevelopmentAccounts(draws, receipts, equity_account, loan)
