from typing import Callable

import numpy as np
from numba import jit
import numba

import pandas as pd

import rangekeeper as rk


class Financial:

    @staticmethod
    def interest(
            amount: float,
            rate: float,
            balance: rk.flux.Flow,
            frequency: rk.duration.Type,
            capitalized: bool = False) -> rk.flux.Flow:
        """
        Calculate interest expense on a loan or other interest-bearing liability.
        Make sure the rate is consistent with the frequency
        """

        balance = balance.resample(frequency=frequency)

        interest_amounts = rk.formula.Financial._calculate_interest(
            amount=np.float64(amount),
            balance=numba.typed.List(balance.movements.to_list()),
            rate=np.float64(rate),
            capitalized=capitalized)

        return rk.flux.Flow(
            name='Interest Expense',
            movements=pd.Series(
                data=interest_amounts,
                index=balance.movements.index),
            units=balance.units)

    @staticmethod
    @numba.jit
    def _calculate_interest(
            amount: np.float64,
            balance: numba.typed.List,
            rate: np.float64,
            capitalized: bool = False) -> numba.typed.List:

        utilized = numba.typed.List()
        interest = numba.typed.List()
        accrued = numba.typed.List()

        for i in range(len(balance)):
            utilized.append(amount - balance[i])

            if capitalized:
                accrued_amount = 0 if i == 0 else accrued[-1]
                interest_amount = 0 if np.isclose(utilized[i], 0) else (utilized[i] + accrued_amount) * rate
                interest.append(interest_amount)
                accrued.append(sum(interest))
            else:
                interest_amount = 0 if np.isclose(utilized[i], 0) else utilized[i] * rate
                interest.append(interest_amount)

        return interest

    @staticmethod
    def balance(
            start_amount: float,
            transactions: rk.flux.Stream,
            name: str = None) -> rk.flux.Stream:

        start_balance = numba.typed.List([np.float64(start_amount)])
        transaction_amounts = numba.typed.List(transactions.sum().movements.to_list())

        balance = rk.formula.Financial._calculate_balance(
            start_balance=start_balance,
            transactions=transaction_amounts)

        balance_flows = [
            rk.flux.Flow.from_sequence(
                sequence=transactions.frame.index,
                data=record,
                units=transactions.sum().units,
                name=name)
            for record, name in zip(balance, ('Start Balance', 'End Balance'))
        ]

        return rk.flux.Stream(
            name=name,
            flows=balance_flows,
            frequency=transactions.frequency)

    @staticmethod
    @numba.jit
    def _calculate_balance(
            start_balance: numba.typed.List,
            transactions: numba.typed.List) -> numba.typed.List:

        end_balance = numba.typed.List()
        for i in range(len(transactions)):
            end_balance.append(start_balance[-1] + transactions[i])
            start_balance.append(end_balance[-1])
        return (start_balance[:-1], end_balance)

    @staticmethod
    def solve_principal(
            desired: float,
            costing: Callable[[float, dict], float],
            params: dict = None) -> float:

        principal = desired
        cost = costing(principal, params)
        delta = not np.isclose(desired - (principal - cost), 0)
        next = desired + cost

        while delta:
            principal = next
            cost = costing(principal, params)
            delta = not np.isclose(desired - (principal - cost), 0)
            next = desired + cost

        return principal