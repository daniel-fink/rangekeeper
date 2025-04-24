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
        self.equity = rk.formula.financial.Balance(
            starting=self.params["equity"],
            transactions=self.draws.sum(),
            frequency=self.params["frequency"],
        )

        self.overdraft = self.equity.overdraft

        self.interest = rk.formula.financial.Interest(
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count((self.params["frequency"])),
            transactions=rk.flux.Stream(
                flows=[self.overdraft.invert(), self.payments.invert()],
                frequency=self.params["frequency"],
            ).sum(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Interest.Type.CAPITALIZED,
        )


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

    def test_compounded_interest(self):
        transactions = rk.flux.Flow.from_sequence(
            name="Transactions",
            data=np.insert(np.full(11, 0), 0, self.params["costs"]),
            sequence=self.model.model_span.to_sequence(
                frequency=self.params["frequency"]
            ),
        )
        interest = rk.formula.financial.Interest(
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count((self.params["frequency"])),
            transactions=transactions,
            frequency=self.params["frequency"],
        )

        interest.balance.startings.display()
        interest.balance.endings.display()
        interest.amounts.display()

        assert interest.balance.endings.movements.iloc[-1] == approx(525580.95)
        assert interest.amounts.total() == approx(25580.95)

    def test_amortized_interest(self):
        amount = -self.params["costs"]
        sequence = self.model.model_span.to_sequence(frequency=self.params["frequency"])
        rate = self.params["interest_rate_pa"] / rk.duration.Period.yearly_count(
            (self.params["frequency"])
        )
        transactions = npf.ppmt(
            rate=rate, per=range(1, sequence.size + 1), nper=sequence.size, pv=amount
        )

        interest = rk.formula.financial.Interest(
            rate=rate,
            transactions=rk.flux.Flow.from_sequence(
                name="Transactions", data=transactions, sequence=sequence
            ),
            frequency=self.params["frequency"],
        )

        assert interest.balance.endings.movements.iloc[-1] == approx(513644.89)
        assert interest.amounts.total() == approx(13644.89)

    def test_capitalized_interest(self):
        interest = rk.formula.financial.Interest(
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count((self.params["frequency"])),
            transactions=self.model.draws.sum().invert(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Interest.Type.CAPITALIZED,
        )
        # assert interest.balance.endings.movements.iloc[-1] == approx(510577.82)
        # assert interest.amounts.total() == approx(10577.82)

        interest.balance.startings.display()
        interest.balance.endings.display()
        interest.amounts.display()
        interest.balance.overdraft.display()

    def test_balance(self):
        transactions = rk.flux.Stream(
            name="Transactions",
            flows=[self.model.draws.sum().invert(), self.model.payments.invert()],
            frequency=self.params["frequency"],
        )
        interest = rk.formula.financial.Interest(
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count((self.params["frequency"])),
            transactions=transactions.sum(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Interest.Type.CAPITALIZED,
        )
        interest.balance.overdraft.display()
        assert interest.balance.overdraft.movements.iloc[-1] == approx(-333333.33)
        assert interest.balance.overdraft.total() == approx(-488680.57)
        assert interest.amounts.total() == approx(11319.43)

        interest.balance.startings.display()
        interest.balance.endings.display()
        interest.amounts.display()

    def test_balances(self):
        transactions = rk.flux.Stream(
            name="Transactions",
            flows=[self.model.draws.sum().invert()],
            frequency=self.params["frequency"],
        )
        equity = rk.formula.financial.Balance(
            starting=176631.99,
            transactions=transactions.sum().invert(),
            frequency=self.params["frequency"],
        )
        assert equity.endings.movements.iloc[2] == approx(9965.32)
        transactions.display()
        equity.startings.display()
        equity.endings.display()

        overdraft = equity.overdraft
        overdraft.display()

        interest = rk.formula.financial.Interest(
            rate=self.params["interest_rate_pa"]
            / rk.duration.Period.yearly_count((self.params["frequency"])),
            transactions=rk.flux.Stream(
                flows=[
                    overdraft.invert(),
                    self.model.payments.invert(),
                ],
                frequency=self.params["frequency"],
            ).sum(),
            frequency=self.params["frequency"],
            type=rk.formula.financial.Interest.Type.CAPITALIZED,
        )
        interest.balance.startings.display()
        interest.balance.endings.display()
        interest.amounts.display()
        print(interest.amounts.total())

        profit = interest.balance.overdraft.invert()
        profit.name = "Profit"
        profit.display()

        assert profit.total() == approx(671969.16)


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
                    date=start_date, duration=rk.duration.Type.MONTH, amount=9
                ),
                payments_periods=3,
                equity=equity,
                acquisition=rlv,
            )
            model = Model(params)
            model.init_transactions()
            model.init_finance()
            finance = model.interest.amounts.total()
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
        assert solution.x[3] == approx(239654.64)
