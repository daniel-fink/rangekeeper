import numpy as np
from numba import jit
import numba

import rangekeeper as rk


class Financial:

    @staticmethod
    def interest(
            amount: float,
            rate_pa: float,
            balance: rk.flux.Flow,
            frequency: rk.duration.Type) -> rk.flux.Flow:

        interest_amounts = rk.formula.Financial._calculate_interest(
            amount=np.float64(amount),
            balance=numba.typed.List(balance.movements.to_list()),
            rate=np.float64(rate_pa / rk.duration.Period.yearly_count(frequency)))

        return rk.flux.Flow.from_dict(
            name='Interest Expense',
            movements=dict(zip(balance.movements.index, interest_amounts)),
            units=balance.units)

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
                units=transactions.sum().units)
            for record in balance
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
    @numba.jit
    def _calculate_interest(
            amount: np.float64,
            balance: numba.typed.List,
            rate: np.float64) -> numba.typed.List:

        utilized = numba.typed.List()
        interest = numba.typed.List()
        accrued = numba.typed.List()

        for i in range(len(balance)):
            utilized.append(amount - balance[i])
            accrued_amount = 0 if i == 0 else accrued[-1]
            interest_amount = 0 if np.isclose(utilized[i], 0) else (utilized[i] + accrued_amount) * rate
            interest.append(interest_amount)
            accrued.append(sum(interest))

        return interest
