import pytest
from pytest import approx
import pandas as pd
import locale

import numpy as np
import numpy_financial as npf
import rangekeeper as rk

# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.

locale.setlocale(locale.LC_ALL, 'en_US')
currency = rk.measure.register_currency(registry=rk.measure.Index.registry)


class TestFormula:
    frequency = rk.duration.Type.YEAR
    loan_amount = 1000000
    interest_rate_pa = 0.05
    draws_span = rk.span.Span.from_duration(
        name='Draws Span',
        date=pd.Timestamp(2020, 1, 1),
        duration=frequency,
        amount=10)
    sequence = draws_span.to_sequence(frequency=frequency)

    def test_compound_interest(self):
        draws = rk.flux.Flow.from_projection(
            name='Draws',
            value=-TestFormula.loan_amount,
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=rk.duration.Sequence.from_bounds(
                    include_start=TestFormula.draws_span.start_date,
                    frequency=TestFormula.frequency,
                    bound=1),
                bounds=(TestFormula.sequence[0], TestFormula.sequence[-1])
            ),
            units=currency.units
        )

        balance = rk.formula.Financial.balance(
            start_amount=TestFormula.loan_amount,
            transactions=rk.flux.Stream(
                name='Transactions',
                flows=[draws],
                frequency=TestFormula.frequency)
        )

        balance.display()
        interest = rk.formula.Financial.interest(
            amount=TestFormula.loan_amount,
            balance=balance.flows[-1],
            rate=TestFormula.interest_rate_pa,
            frequency=TestFormula.frequency,
            capitalized=True)

        interest.display()
        print(interest.movements.sum())

        assert interest.movements.iloc[0] == 50000
        assert interest.movements.sum() == 628894.6267774414

    def test_amortized_interest(self):
        draws = rk.flux.Flow.from_projection(
            name='Draws',
            value=-TestFormula.loan_amount,
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=rk.duration.Sequence.from_bounds(
                    include_start=TestFormula.draws_span.start_date,
                    frequency=TestFormula.frequency,
                    bound=1),
                bounds=(
                    TestFormula.draws_span.start_date.to_period(freq=rk.duration.Type.period(TestFormula.frequency)),
                    TestFormula.draws_span.end_date.to_period(freq=rk.duration.Type.period(TestFormula.frequency))
                )
            ),
            units=currency.units
        )

        payments = rk.flux.Flow(
            name='Payments',
            movements=pd.Series(
                data=npf.ppmt(
                    rate=TestFormula.interest_rate_pa,
                    per=np.arange(1, TestFormula.sequence.size + 1),
                    nper=TestFormula.sequence.size,
                    pv=TestFormula.loan_amount),
                index=TestFormula.sequence.to_timestamp()),
            units=currency.units
        ).invert()
        payments.display()

        balance = rk.formula.Financial.balance(
            start_amount=TestFormula.loan_amount,
            transactions=rk.flux.Stream(
                name='Transactions',
                flows=[draws, payments],
                frequency=TestFormula.frequency)
        )
        balance.display()

        interest = rk.formula.Financial.interest(
            amount=TestFormula.loan_amount,
            balance=balance.flows[-1],
            rate=TestFormula.interest_rate_pa,
            frequency=TestFormula.frequency)

        interest.display()
        print(interest.movements.sum())

    def test_capitalized_interest(self):
        loan_amount = 1000000
        interest_rate_pm = 0.05 / 12
        draws_span = rk.span.Span.from_duration(
            name='Draws Span',
            date=pd.Timestamp(2020, 1, 1),
            duration=rk.duration.Type.MONTH,
            amount=9)
        payments_span = rk.span.Span.from_duration(
            name='Payments Span',
            date=rk.duration.offset(
                date=draws_span.end_date,
                duration=rk.duration.Type.DAY),
            duration=rk.duration.Type.MONTH,
            amount=3)

        draws = rk.flux.Flow.from_projection(
            name='Draws',
            value=-loan_amount,
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=draws_span.to_sequence(frequency=rk.duration.Type.MONTH)),
            units=currency.units
        )
        payments = rk.flux.Flow.from_projection(
            name='Payments',
            value=loan_amount,
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=payments_span.to_sequence(frequency=rk.duration.Type.MONTH)),
            units=currency.units
        )

        balance = rk.formula.Financial.balance(
            start_amount=loan_amount,
            transactions=rk.flux.Stream(
                name='Transactions',
                flows=[draws, payments],
                frequency=rk.duration.Type.MONTH)
        )

        interest_flow = rk.formula.Financial.interest(
            amount=loan_amount,
            balance=balance.flows[-1],
            rate=interest_rate_pm,
            frequency=rk.duration.Type.MONTH,
            capitalized=True)

        balance.display()
        interest_flow.display()
        print(draws.movements.sum())
        print(payments.movements.sum())
