"""Migrated known-data development account example, independent of legacy modules."""

from rangekeeper.calculations.account import Account

from dataclasses import dataclass
from datetime import date
from rangekeeper.model.flow import Flow
from rangekeeper.model.measure import Quantity
from rangekeeper.duration import make_periods
from rangekeeper.calculations import projection, series, account


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
    starting=date(2020, 1, 1)
) -> DevelopmentAccounts:
    """Nine monthly draws, three repayments; advance transactions and capitalized debt."""
    periods = make_periods(starting, frequency="month", count=12)
    purchase = projection.allocate(
        Quantity(magnitude=-acquisition, units="AUD"), periods=periods[:1]
    )
    construction = projection.allocate(
        Quantity(magnitude=-costs, units="AUD"), periods=periods[:9]
    )
    draws = series.aggregate(
        (purchase, construction), join="union", missing="zero"
    ).flow
    receipts = projection.allocate(
        Quantity(magnitude=payments, units="AUD"), periods=periods[9:]
    )
    equity_account = Account.calculate(
        draws, starting=Quantity(magnitude=equity, units="AUD")
    )
    debt = series.aggregate(
        (equity_account.overdraft.negate(), receipts.negate()),
        join="union",
        missing="zero",
    ).flow
    loan = Account.calculate(
        debt,
        starting=Quantity(magnitude=0, units="AUD"),
        rate=interest_rate / 12,
        method="capitalized",
    )
    return DevelopmentAccounts(draws, receipts, equity_account, loan)
