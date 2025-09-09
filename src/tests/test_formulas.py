import pytest
from pytest import approx
import pandas as pd
import locale

import numpy as np
import numpy_financial as npf

import rangekeeper as rk
import scipy.optimize as opt

# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.

locale.setlocale(locale.LC_ALL, "en_US")
currency = rk.measure.register_currency(registry=rk.measure.Index.registry)


class Model:
    params: dict

    def __init__(self, params: dict):
        self.params = params

    def init_transactions(self):
        self.params["revenue"] = (
            0 if "revenue" not in self.params else self.params["revenue"]
        )

        self.draws_span = rk.duration.Span.from_duration(
            name="Draws Span",
            date=self.params["start_date"],
            duration=self.params["frequency"],
            amount=self.params["draws_periods"],
        )
        self.payments_span = rk.duration.Span.from_duration(
            name="Payments Span",
            date=self.params["payments_start_date"],
            duration=self.params["frequency"],
            amount=self.params["payments_periods"],
        )
        self.model_span = rk.duration.Span(
            name="Span",
            start_date=self.params["start_date"],
            end_date=self.payments_span.end_date,
        )

        self.acquisition = rk.flux.Flow.from_projection(
            name="Acquisition",
            value=-self.params["acquisition"],
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=pd.PeriodIndex(
                    [self.draws_span.to_sequence(frequency=self.params["frequency"])[0]]
                ),
            ),
            units=currency.units,
        )
        self.costs = rk.flux.Flow.from_projection(
            name="Development Costs",
            value=-self.params["costs"],
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=self.draws_span.to_sequence(
                    frequency=self.params["frequency"]
                ),
            ),
            units=currency.units,
        )
        self.draws = rk.flux.Stream(
            name="Draws",
            flows=[self.acquisition, self.costs],
            frequency=self.params["frequency"],
        )

        self.payments = rk.flux.Flow.from_projection(
            name="Payments",
            value=self.params["payments"],
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=self.payments_span.to_sequence(
                    frequency=self.params["frequency"]
                ),
            ),
            units=currency.units,
        )

    def init_finance(self):
        self.equity = rk.formula.financial.Account(
            starting=self.params["equity"],
            transactions=self.draws.sum(),
            frequency=self.params["frequency"],
            name="Equity Account",
        )

        self.loan = rk.formula.financial.Account(
            starting=0,
            transactions=rk.flux.Stream(
                flows=[
                    self.equity.overdraft.diff().negate(),
                    self.payments.negate(),
                ],
                frequency=self.params["frequency"],
            ).sum(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Account.Type.CAPITALIZED,
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count((self.params["frequency"])),
            name="Loan Account",
        )

        #
        #
        # self.equity = rk.formula.financial.Balance(
        #     starting=self.params["equity"],
        #     transactions=self.draws.sum(),
        #     frequency=self.params["frequency"],
        # )
        #
        # self.overdraft = self.equity.overdraft

        # self.interest = rk.formula.financial.Interest(
        #     rate=self.params["interest_rate_pa"]
        #     / rk.duration.Period.yearly_count((self.params["frequency"])),
        #     transactions=rk.flux.Stream(
        #         flows=[self.overdraft.invert(), self.payments.invert()],
        #         frequency=self.params["frequency"],
        #     ).sum(),
        #     frequency=self.params["frequency"],
        #     type=rk.formula.financial.Interest.Type.CAPITALIZED,
        # )


class TestFinancial:
    # Parameters:
    value = 1e6
    start_date = pd.Timestamp(2020, 1, 1)
    params = dict(
        frequency=rk.duration.Type.MONTH,
        acquisition=0,
        costs=value / 2,
        interest_rate_pa=0.05,
        start_date=start_date,
        draws_periods=9,
        payments=value,
        payments_start_date=rk.duration.offset(
            date=start_date,
            duration=rk.duration.Type.MONTH,
            amount=9,
        ),
        payments_periods=3,
    )

    model = Model(params)
    model.init_transactions()

    def test_simple_interest(self):
        transactions = rk.flux.Stream(
            name="Transactions",
            flows=[
                self.model.draws.sum(),
                self.model.payments,
            ],
            frequency=self.params["frequency"],
        )
        transactions.display()

        cash_account = rk.formula.financial.Account(
            starting=0,
            transactions=transactions.sum(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Account.Type.SIMPLE,
            name="Cash Account",
        )
        cash_account.startings.display()
        cash_account.endings.display()
        cash_account.overdraft.display()
        cash_account.interest.display()

        interest_account = rk.formula.financial.Account(
            starting=0,
            transactions=transactions.sum(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Account.Type.SIMPLE,
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count(duration=self.params["frequency"]),
            name="Interest Account",
        )
        interest_account.startings.display()
        interest_account.endings.display()
        interest_account.overdraft.display()
        interest_account.interest.display()

        assert interest_account.endings.movements.iloc[-1] == approx(500000.00)
        assert interest_account.interest.total().magnitude == approx(
            694.44 + 2083.33, rel=1e-2
        )

    def test_compounded_interest(self):
        transactions = rk.flux.Flow.from_sequence(
            name="Transactions",
            data=np.insert(
                np.full(11, 0),
                0,
                self.params["costs"],
            ),
            sequence=self.model.model_span.to_sequence(
                frequency=self.params["frequency"]
            ),
            units=currency.units,
        )

        account = rk.formula.financial.Account(
            starting=0,
            transactions=transactions,
            frequency=self.params["frequency"],
            type=rk.formula.financial.Account.Type.COMPOUND,
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count(duration=self.params["frequency"]),
            name="Compound Interest Account",
        )
        transactions.display()
        account.startings.display()
        account.endings.display()
        account.overdraft.display()
        account.interest.display()

        assert account.endings.movements.iloc[-1] == approx(525580.95)
        assert account.interest.total().magnitude == approx(25580.95)

    def test_amortized_loan(self):
        amount = self.params["costs"]
        sequence = self.model.model_span.to_sequence(frequency=self.params["frequency"])
        rate = self.params["interest_rate_pa"] / rk.duration.Period.yearly_count(
            (self.params["frequency"])
        )
        transactions = npf.ppmt(
            rate=rate,
            per=range(1, sequence.size + 1),
            nper=sequence.size,
            pv=-amount,
        )
        print(transactions)

        account = rk.formula.financial.Account(
            starting=amount,
            transactions=rk.flux.Flow.from_sequence(
                name="Transactions",
                data=transactions,
                sequence=sequence,
                units=currency.units,
            ).negate(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Account.Type.SIMPLE,
            rate=rate,
            name="Amortized Loan Account",
            arrears=True,
        )
        account.startings.display()
        account.endings.display()
        account.overdraft.display()
        account.interest.display()

        payment = npf.pmt(
            rate=rate,
            nper=sequence.size,
            pv=-amount,
        )

        assert account.endings.movements.iloc[-1] == approx(0.00)
        assert transactions[0] + account.interest.movements.iloc[0] == approx(payment)
        assert account.interest.total().magnitude == approx(13644.89)

    def test_capitalized_interest(self):
        account = rk.formula.financial.Account(
            starting=0,
            transactions=self.model.draws.sum().negate(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Account.Type.CAPITALIZED,
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count((self.params["frequency"])),
            name="Capitalized Interest Account",
        )

        account.startings.display()
        account.endings.display()
        account.overdraft.display()
        account.interest.display()

        assert account.endings.movements.iloc[-1] == approx(510577.82)
        assert account.interest.total().magnitude == approx(10577.82)

    def test_balance(self):
        transactions = rk.flux.Stream(
            name="Transactions",
            flows=[
                self.model.draws.sum().negate(),
                self.model.payments.negate(),
            ],
            frequency=self.params["frequency"],
        )

        transactions.display()
        transactions.sum().display()

        account = rk.formula.financial.Account(
            starting=0,
            transactions=transactions.sum(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Account.Type.CAPITALIZED,
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count((self.params["frequency"])),
        )

        account.startings.display()
        account.endings.display()
        account.overdraft.display()
        account.interest.display()

        assert account.overdraft.movements.iloc[-1] == approx(-488680.57)
        assert account.interest.total().magnitude == approx(11319.43)

    def test_balances(self):
        transactions = rk.flux.Stream(
            name="Transactions",
            flows=[self.model.draws.sum().negate()],
            frequency=self.params["frequency"],
        )

        equity = rk.formula.financial.Account(
            starting=176631.99,
            transactions=transactions.sum().negate(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Account.Type.SIMPLE,
            name="Equity Account",
        )

        assert equity.endings.movements.iloc[2] == approx(9965.32)
        transactions.display()
        equity.startings.display()
        equity.endings.display()
        equity.overdraft.display()
        equity.overdraft.diff().display()

        loan = rk.formula.financial.Account(
            starting=0,
            transactions=rk.flux.Stream(
                flows=[
                    equity.overdraft.diff().negate(),
                    self.model.payments.negate(),
                ],
                frequency=self.params["frequency"],
            ).sum(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Account.Type.CAPITALIZED,
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count((self.params["frequency"])),
            name="Loan Account",
        )
        loan.startings.display()
        loan.endings.display()
        loan.overdraft.display()
        loan.interest.display()
        print(loan.interest.total())

        profit = rk.flux.Stream(
            flows=[
                equity.diff(),
                loan.overdraft.diff().negate(),
            ],
            frequency=self.params["frequency"],
            name="Profit",
        )
        profit.display()

        assert profit.sum().total().magnitude == approx(495337.17)


class TestSolver:
    def test_residual(self):
        start_date = pd.Timestamp(2020, 1, 1)
        sales = 1e6
        dev = sales / 2
        margin = 0.25
        ltc = 0.65

        def solve(values):
            loan, equity, profit, rlv = values

            params = dict(
                frequency=rk.duration.Type.MONTH,
                costs=dev,
                interest_rate_pa=0.05,
                start_date=start_date,
                draws_periods=9,
                payments=sales,
                payments_start_date=rk.duration.offset(
                    date=start_date,
                    duration=rk.duration.Type.MONTH,
                    amount=9,
                ),
                payments_periods=3,
                equity=equity,
                acquisition=rlv,
            )
            model = Model(params)
            model.init_transactions()
            model.init_finance()
            finance = model.loan.interest.total().magnitude
            sources = equity + loan
            uses = dev + finance + rlv

            return [
                abs(sources - uses),
                abs(loan - (uses * ltc)),
                abs(profit - (sales * margin)),
                abs(rlv - (sales - dev - finance - profit)),
            ]

        guess = [dev, dev, sales * margin, 0]  # loan  # equity  # profit  # rlv
        solution = opt.root(solve, guess, method="lm")  # , options={'disp': True})
        results = {
            "loan": solution.x[0],
            "equity": solution.x[1],
            "profit": solution.x[2],
            "rlv": solution.x[3],
        }
        print(
            "\n".join([f"{k}: {rk.format.to_currency(v)}" for k, v in results.items()])
        )

        assert solution.success
        assert solution.x[0] == approx(487500)
        assert solution.x[1] == approx(262500)
        assert solution.x[2] == approx(250000)
        assert solution.x[3] == approx(241049.33)
