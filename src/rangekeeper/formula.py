from typing import Callable, Optional

import numpy as np
from numba import jit
import numba
import pandas as pd
import scipy.optimize as opt

import rangekeeper as rk


class Financial:

    @staticmethod
    def interest(
            rate: float,
            transactions: rk.flux.Flow,
            frequency: rk.duration.Type,
            capitalized: bool = False) -> (rk.flux.Stream, rk.flux.Flow):
        """
        Calculate interest expense on a loan or other interest-bearing liability,
        described by a series of transactions.
        Assumes interest is compounded on a positive, outstanding balance per period
        (i.e. draws are positive, payments are negative).
        Make sure the rate is consistent with the frequency.
        """

        transactions = transactions.resample(frequency=frequency)

        startings, endings, interests = rk.formula.Financial._calc_interest(
            transactions=numba.typed.List(transactions.movements.to_list()),
            rate=np.float64(rate),
            capitalized=capitalized)

        balance = rk.flux.Stream(
            name='Balance',
            flows=[
                rk.flux.Flow(
                    movements=pd.Series(startings, index=transactions.movements.index),
                    units=transactions.units,
                    name='Start Balance'),
                rk.flux.Flow(
                    movements=pd.Series(endings, index=transactions.movements.index),
                    units=transactions.units,
                    name='End Balance')
            ],
            frequency=frequency)

        interest = rk.flux.Flow(
            movements=pd.Series(interests, index=transactions.movements.index),
            units=transactions.units,
            name='Interest')

        return (balance, interest)


    @staticmethod
    @numba.jit
    def _calc_interest(
            transactions: numba.typed.List,
            rate: np.float64,
            capitalized: bool = False) -> (numba.typed.List, numba.typed.List, numba.typed.List):

        startings = numba.typed.List.empty_list(numba.float64)
        endings = numba.typed.List.empty_list(numba.float64)
        interests = numba.typed.List.empty_list(numba.float64)

        for i in range(len(transactions)):
            if i == 0:
                startings.append(0)
            else:
                startings.append(endings[-1])
            principal = startings[i] + transactions[i]
            if capitalized:
                interest = (principal * rate) / (1 - rate) if principal > 0 else 0 # Since we are capitalizing interest, the interest amount (draw) must include interest to pay on the principal. Derived from i = r * (P + i)
                endings.append(principal + interest)
            else:
                interest = principal * rate if principal > 0 else 0
                endings.append(principal + interest)
            interests.append(interest)

        return (startings, endings, interests)


    @staticmethod
    def balance(
            starting: float,
            transactions: rk.flux.Flow,
            frequency: rk.duration.Type,
            name: str = None) -> rk.flux.Stream:#, rk.flux.Flow):
        """
        Calculate the balance of a financial account given a starting balance and a series of transactions.
        """

        starting = numba.typed.List([np.float64(starting)])
        transaction_amounts = numba.typed.List(transactions.movements.to_list())

        balance = rk.formula.Financial._calculate_balance(
            starting=starting,
            transactions=transaction_amounts)

        flows = [
            rk.flux.Flow(
                movements=pd.Series(record, index=transactions.movements.index),
                units=transactions.units,
                name=name)
            for record, name in zip(balance, ('Start Balance', 'End Balance'))
        ]

        statement = rk.flux.Stream(
            name=name,
            flows=flows,
            frequency=frequency)

        return statement

    @staticmethod
    @numba.jit
    def _calculate_balance(
            starting: numba.typed.List,
            transactions: numba.typed.List) -> (numba.typed.List, numba.typed.List):

        ending = numba.typed.List.empty_list(numba.float64)
        for i in range(len(transactions)):
            ending.append(float(starting[-1] + transactions[i]))
            starting.append(ending[-1])
        return (starting[:-1], ending)

    @staticmethod
    def overdraft(
            balance: rk.flux.Stream,
            name: str = None) -> rk.flux.Flow:
        """
        Identifies the portion of transactions occurring while the balance is negative.
        """
        if len(balance.flows) != 2:
            raise ValueError('Balance must be Stream with two flows; Start and End.')
        if balance.flows[0].units != balance.flows[1].units:
            raise ValueError('Units of the Start and End Flows must be the same.')

        starts = balance.flows[0].movements.where(balance.flows[0].movements < 0).fillna(0)
        ends = balance.flows[1].movements.where(balance.flows[1].movements < 0).fillna(0)

        return rk.flux.Flow(
            movements=ends - starts,
            units=balance.flows[0].units,
            name='Overdraft' if name is None else name)
