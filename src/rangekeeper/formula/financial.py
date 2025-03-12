import enum
import dataclasses
import numpy as np
import numba
import pandas as pd

import rangekeeper as rk


class Balance:
    startings: rk.flux.Flow
    endings: rk.flux.Flow

    def __init__(
            self,
            starting: float,
            transactions: rk.flux.Flow,
            frequency: rk.duration.Type,
    ):
        """
        Calculate the balance of a financial account given a starting balance and a series of transactions.
        """

        transactions = transactions.resample(frequency=frequency)

        result = self._calculate_balance(
            startings=numba.typed.List([np.float64(starting)]),
            transactions=numba.typed.List(transactions.movements.to_list()))

        self.startings=rk.flux.Flow(
            movements=pd.Series(result[0], index=transactions.movements.index),
            units=transactions.units,
            name='Start Balance')

        self.endings=rk.flux.Flow(
            movements=pd.Series(result[1], index=transactions.movements.index),
            units=transactions.units,
            name='End Balance')

    @classmethod
    def from_flows(
            cls,
            startings: rk.flux.Flow,
            endings: rk.flux.Flow,
    ):
        balance = super().__new__(cls)
        balance.startings = startings
        balance.endings = endings

        return balance

    def overdraft(
            self,
            name: str = None,
    ) -> rk.flux.Flow:
        """
        Identifies the portion of transactions occurring while the balance is negative.
        """

        starts = self.startings.movements.where(self.startings.movements < 0).fillna(0)
        ends = self.endings.movements.where(self.endings.movements < 0).fillna(0)

        overdrafts = ends - starts
        overdrafts = overdrafts.where(overdrafts < 0).dropna()

        return rk.flux.Flow(
            movements=overdrafts,
            units=self.startings.units,
            name='Overdraft' if name is None else name)


    @staticmethod
    @numba.jit
    def _calculate_balance(
            startings: numba.typed.List,
            transactions: numba.typed.List) -> (numba.typed.List, numba.typed.List):

        endings = numba.typed.List.empty_list(numba.float64)
        for i in range(len(transactions)):
            endings.append(float(startings[-1] + transactions[i]))
            startings.append(endings[-1])

        return (startings[:-1], endings)


class Interest:
    amounts: rk.flux.Flow
    balance: Balance

    class Type(enum.Enum):
        INTEREST_ONLY = 'interest_only'
        COMPOUND = 'compound'
        CAPITALIZED = 'capitalized'

    def __init__(
            self,
            rate: float | rk.flux.Flow,
            transactions: rk.flux.Flow,
            frequency: rk.duration.Type,
            type: Type = Type.COMPOUND,
    ):
        """
        Calculate interest expense on a loan or other interest-bearing liability,
        described by a series of transactions.
        Assumes interest is compounded on a positive, outstanding balance per period
        (i.e. draws are positive, payments are negative).
        Make sure the rate is consistent with the frequency.
        """

        transactions = transactions.resample(frequency=frequency)

        if isinstance(rate, float):
            rate = rk.flux.Flow.from_projection(
                name='Interest Rates',
                value=rate,
                proj=rk.projection.Extrapolation(
                    form=rk.extrapolation.Recurring(),
                    sequence=rk.duration.Sequence.from_datestamps(
                        datestamps=transactions.movements.index,
                        frequency=frequency)))
        else:
            raise NotImplementedError('Only float rates are supported currently.')

        if len(transactions.movements) != len(rate.movements):
            raise ValueError('The number of transactions must match the number of rates.')

        startings, endings, interests = self._calc_interest(
            transactions=numba.typed.List(transactions.movements.to_list()),
            rates=numba.typed.List(rate.movements.to_list()),
            type=type.value)

        self.balance = rk.formula.financial.Balance.from_flows(
            startings=rk.flux.Flow(
                movements=pd.Series(startings, index=transactions.movements.index),
                units=transactions.units,
                name='Start Balance'),
            endings=rk.flux.Flow(
                movements=pd.Series(endings, index=transactions.movements.index),
                units=transactions.units,
                name='End Balance')
        )

        self.amounts = rk.flux.Flow(
            movements=pd.Series(interests, index=transactions.movements.index),
            units=transactions.units,
            name='Interest')


    @staticmethod
    @numba.jit
    def _calc_interest(
            transactions: numba.typed.List,
            rates: numba.typed.List,
            type: str,
    ) -> (numba.typed.List, numba.typed.List, numba.typed.List):

        startings = numba.typed.List.empty_list(numba.float64)
        endings = numba.typed.List.empty_list(numba.float64)
        amounts = numba.typed.List.empty_list(numba.float64)

        for i in range(len(transactions)):
            if i == 0:
                startings.append(0)
            else:
                startings.append(endings[-1])

            principal = startings[i] + transactions[i]
            if type == 'interest_only':
                interest = principal * rates[i] if principal > 0 else 0
                endings.append(principal)

            elif type == 'compound':
                interest = principal * rates[i] if principal > 0 else 0
                endings.append(principal + interest)

            elif type == 'capitalized':
                interest = (principal * rates[i]) / (1 - rates[i]) if principal > 0 else 0 # Since we are capitalizing
                # interest, the amount (draw) must include interest to pay on the principal. Derived from i = r * (P + i)
                endings.append(principal + interest)

            else:
                raise ValueError(f'Invalid instrument: {type}')

            amounts.append(interest)

        return (startings, endings, amounts)



