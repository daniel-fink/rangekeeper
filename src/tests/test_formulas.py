"""Migrated financial examples with explicit periods, units and account equations."""

from rangekeeper.model.duration import Frequency
from rangekeeper.calculations.series import AlignmentJoin
from rangekeeper.model.flow import MissingValueHandling
from rangekeeper.calculations.account import Balance, CurrentInterest, InterestTreatment

from rangekeeper.calculations.account import Account
from rangekeeper.model.flow import Flow

from datetime import date
import math
import numpy_financial as npf
from scipy.optimize import brentq
from pytest import approx

from rangekeeper.model.measure import Quantity
from rangekeeper.model.duration import make_periods
from rangekeeper.calculations import series, account
from tests.models.financial import build_accounts


class TestFinancial:
    def test_simple_interest(self):
        example = build_accounts()
        transactions = series.aggregate(
            (example.draws, example.payments),
            join=AlignmentJoin.UNION,
            missing=MissingValueHandling.ZERO,
        ).flow
        result = Account.calculate(
            transactions, starting=Quantity(magnitude=0, units="AUD"), rate=0.05 / 12
        )
        assert result.closing.movements[-1].magnitude == approx(500000)
        assert result.interest.total().magnitude == approx(694.44 + 2083.33, rel=1e-2)

    def test_compounded_interest(self):
        periods = make_periods(date(2020, 1, 1), frequency=Frequency.MONTH, count=12)
        transactions = Flow.from_periods(periods, [500000] + [0] * 11, units="AUD")
        result = Account.calculate(
            transactions,
            starting=Quantity(magnitude=0, units="AUD"),
            rate=0.05 / 12,
            treatment=InterestTreatment.FINANCED,
        )
        assert result.closing.movements[-1].magnitude == approx(525580.95)
        assert result.interest.total().magnitude == approx(25580.95)

    def test_amortized_loan(self):
        periods = make_periods(date(2020, 1, 1), frequency=Frequency.MONTH, count=12)
        payments = [float(x) for x in npf.ppmt(0.05 / 12, range(1, 13), 12, -500000)]
        result = Account.calculate(
            Flow.from_periods(periods, [-x for x in payments], units="AUD"),
            starting=Quantity(magnitude=500000, units="AUD"),
            rate=0.05 / 12,
            balance=Balance.OPENING,
        )
        assert result.closing.movements[-1].magnitude == approx(0, abs=1e-7)
        assert payments[0] + result.interest.movements[0].magnitude == approx(
            npf.pmt(0.05 / 12, 12, -500000)
        )
        assert result.interest.total().magnitude == approx(13644.89)

    def test_capitalized_interest(self):
        example = build_accounts()
        result = Account.calculate(
            example.draws.negate(),
            starting=Quantity(magnitude=0, units="AUD"),
            rate=0.05 / 12,
            current_interest=CurrentInterest.INCLUDED,
            treatment=InterestTreatment.FINANCED,
        )
        assert result.closing.movements[-1].magnitude == approx(510577.82)
        assert result.interest.total().magnitude == approx(10577.82)

    def test_balance(self):
        example = build_accounts()
        assert example.loan.overdraft.movements[-1].magnitude == approx(-333333.33)
        assert example.loan.interest.total().magnitude == approx(11319.43)

    def test_balances(self):
        example = build_accounts(equity=176631.99)
        assert example.equity.closing.movements[2].magnitude == approx(9965.32)
        profit = series.aggregate(
            (example.equity.difference(), example.loan.overdraft.negate()),
            join=AlignmentJoin.UNION,
            missing=MissingValueHandling.ZERO,
        ).flow
        assert profit.total().magnitude == approx(495337.17)


def independent_finance(land):
    """Plain scalar cash/debt recurrence, separate from RK's account implementation."""
    cash, debt, interest = 262500.0, 0.0, 0.0
    for month in range(12):
        cost = (500000 / 9 if month < 9 else 0) + (land if month == 0 else 0)
        used = min(cash, cost)
        cash -= used
        principal = debt + cost - used - (1000000 / 3 if month >= 9 else 0)
        charge = max(principal, 0) * (0.05 / 12) / (1 - 0.05 / 12)
        debt = principal + charge
        interest += charge
    return interest


class TestSolver:
    def test_residual(self):
        """Solve the stated accounting equations; reject the old inconsistent expectation."""
        expected = brentq(
            lambda land: land + independent_finance(land) - 250000, 0, 250000
        )

        def residual(land):
            example = build_accounts(acquisition=land, equity=262500)
            return land + example.loan.interest.total().magnitude - 250000

        result = brentq(residual, 0, 250000)
        assert result == approx(expected, abs=1e-6)
        assert result == approx(239654.64260783806, abs=1e-6)
        assert abs(residual(result)) < 1e-6
        # The old 241049.33 expectation does not satisfy its own finance equation.
        assert 241049.33 + independent_finance(241049.33) - 250000 == approx(
            1454.1535992423
        )
