from __future__ import annotations

import enum
from typing import Union

import numba
import numpy as np
import pandas as pd
import pint

import rangekeeper as rk


class Account:
    startings: rk.flux.Flow
    endings: rk.flux.Flow
    overdraft: rk.flux.Flow
    interest: rk.flux.Flow

    @staticmethod
    # @numba.jit
    def _calculate(
        starting: float,
        transactions: numba.typed.List,
        rates: numba.typed.List,
        type: str,
        arrears: bool = False,
    ) -> (
        numba.typed.List,
        numba.typed.List,
        numba.typed.List,
        numba.typed.List,
    ):
        """
        Calculate the balance of a financial account given a starting balance and a series of transactions.
        Returns a tuple of (startings, endings, overdraft, interest) as `numba.typed.List`s
        """
        startings = numba.typed.List.empty_list(numba.float64)
        endings = numba.typed.List.empty_list(numba.float64)
        overdrafts = numba.typed.List.empty_list(numba.float64)
        interests = numba.typed.List.empty_list(numba.float64)

        for i in range(len(transactions)):
            if i == 0:
                principal = starting + (0 if arrears else transactions[i])
                startings.append(np.float64(starting) if starting > 0 else 0)
            else:
                startings.append(endings[-1])
                principal = (
                    overdrafts[-1] + startings[i] + (0 if arrears else transactions[i])
                )
                # overdrafts.append(overdrafts[-1])

            # principal = overdrafts[-1] + startings[i] + transactions[i]
            if type == "simple":
                interest = principal * rates[i] if principal > 0 else 0
                principal = principal

            elif type == "compound":
                interest = principal * rates[i] if principal > 0 else 0
                principal = principal + interest
                # endings.append(principal + interest)

            elif type == "capitalized":
                # Since we are capitalizing interest, the amount (draw) must include interest to pay on the principal.
                # Derived from i = r * (P + i)
                interest = (
                    (principal * rates[i]) / (1 - rates[i]) if principal > 0 else 0
                )
                principal = principal + interest
                # endings.append(principal + interest)

            else:
                raise ValueError(f"Invalid instrument: {type}")

            if arrears:
                principal += transactions[i]

            if principal < 0:
                overdrafts.append(principal)
                endings.append(0)
            else:
                overdrafts.append(0)
                endings.append(principal)

            interests.append(interest)

        return (startings, endings, overdrafts, interests)

    class Type(enum.Enum):
        SIMPLE = "simple"
        COMPOUND = "compound"
        CAPITALIZED = "capitalized"

    def __init__(
        self,
        transactions: rk.flux.Flow,
        frequency: rk.duration.Type,
        starting: Union[float, pint.Quantity] = 0.0,
        rate: Union[float, rk.flux.Flow] = 0.0,
        type: Type = Type.SIMPLE,
        arrears: bool = False,
        name: str = "",
    ):
        transactions = transactions.resample(frequency=frequency)
        name = f"{name.strip()} "  # Add space to end of name

        if isinstance(rate, float):
            rate = rk.flux.Flow.from_projection(
                name=f"{name}Interest Rates",
                value=rate,
                proj=rk.projection.Extrapolation(
                    form=rk.extrapolation.Recurring(),
                    sequence=rk.duration.Sequence.from_datestamps(
                        datestamps=transactions.movements.index,
                        frequency=frequency,
                    ),
                ),
            )
        else:
            assert len(rate.movements.index) == len(
                transactions.movements.index
            ), "Rate must be a Flow with the same number of periods as transactions."

        if isinstance(starting, pint.Quantity):
            if starting.units != transactions.units:
                raise ValueError(
                    f"Starting balance units {starting.units} do not match transaction units {transactions.units}."
                )
            starting = starting.magnitude

        startings, endings, overdraft, interest = self._calculate(
            starting=starting,
            transactions=numba.typed.List(transactions.movements.to_list()),
            rates=numba.typed.List(rate.movements.to_list()),
            type=type.value,
            arrears=arrears,
        )

        self.name = f"{name}Account"

        startings = rk.flux.Flow(
            movements=pd.Series(
                startings,
                index=transactions.movements.index,
            ),
            units=transactions.units,
            name=f"{name}Start Balance",
        )
        self.startings = startings.clean()

        endings = rk.flux.Flow(
            movements=pd.Series(
                endings,
                index=transactions.movements.index,
            ),
            units=transactions.units,
            name=f"{name}End Balance",
        )
        self.endings = endings.clean()

        overdraft = rk.flux.Flow(
            movements=pd.Series(
                overdraft,
                index=transactions.movements.index,
            ),
            units=transactions.units,
            name=f"{name}Overdraft",
        )
        self.overdraft = overdraft.clean()

        interest = rk.flux.Flow(
            movements=pd.Series(
                interest,
                index=transactions.movements.index,
            ),
            units=transactions.units,
            name=f"{name}Interest Amounts",
        )
        self.interest = interest.clean()

    def diff(
        self,
        name: str = None,
    ) -> rk.flux.Flow:
        """
        Calculate the difference between the start and end balances.
        """
        name = self.name if name is None else name
        result = rk.flux.Flow(
            movements=self.endings.movements - self.startings.movements,
            units=self.startings.units,
            name=f"{self.startings.name} (diff)",
        )
        return result.clean()


# class Balance:
#     startings: rk.flux.Flow
#     endings: rk.flux.Flow
#     overdraft: rk.flux.Flow
#
#     def __init__(
#         self,
#         starting: float,
#         transactions: rk.flux.Flow,
#         frequency: rk.duration.Type,
#         name: str = "",
#     ):
#         """
#         Calculate the balance of a financial account given a starting balance and a series of transactions.
#         Returns an object with the starting and ending balances, as well as the overdraft amount, as `Flow`s.
#         Overdraft is the portion of transactions occurring while the balance is non-positive.
#         """
#
#         transactions = transactions.resample(frequency=frequency)
#
#         result = self._calculate_balance(
#             startings=numba.typed.List([np.float64(starting)]),
#             transactions=numba.typed.List(transactions.movements.to_list()),
#         )
#
#         self.startings = rk.flux.Flow(
#             movements=pd.Series(
#                 result[0],
#                 index=transactions.movements.index,
#             ),
#             units=transactions.units,
#             name=f"{name} Start Balance",
#         )
#
#         self.endings = rk.flux.Flow(
#             movements=pd.Series(
#                 result[1],
#                 index=transactions.movements.index,
#             ),
#             units=transactions.units,
#             name=f"{name} End Balance",
#         )
#
#         self.overdraft = rk.flux.Flow(
#             movements=pd.Series(
#                 result[2],
#                 index=transactions.movements.index,
#             ),
#             units=transactions.units,
#             name=f"{name} Overdraft",
#         )
#
#     @classmethod
#     def from_flows(
#         cls,
#         startings: rk.flux.Flow,
#         endings: rk.flux.Flow,
#         frequency: rk.duration.Type,
#         name: str = "",
#     ):
#         name = startings.name if name is None else name
#         if startings.units != endings.units:
#             raise ValueError("The units of the starting and ending flows must match.")
#         units = startings.units
#
#         startings = startings.resample(frequency=frequency)
#         endings = endings.resample(frequency=frequency)
#
#         transactions = rk.flux.Flow(
#             movements=endings.movements - startings.movements,
#             units=units,
#         )
#         starting = startings.movements.iloc[0]
#
#         return cls(
#             starting=starting,
#             transactions=transactions,
#             frequency=frequency,
#             name=name,
#         )
#
#     @staticmethod
#     @numba.jit
#     def _calculate_balance(
#         startings: numba.typed.List,
#         transactions: numba.typed.List,
#     ) -> (
#         numba.typed.List,
#         numba.typed.List,
#         numba.typed.List,
#     ):
#
#         endings = numba.typed.List.empty_list(numba.float64)
#         overdrafts = numba.typed.List.empty_list(numba.float64)
#         for i in range(len(transactions)):
#             ending = float(startings[-1] + transactions[i])
#
#             overdrafts.append(ending if ending < 0 else 0)
#             endings.append(ending if ending > 0 else 0)
#             startings.append(endings[-1])
#
#         return (
#             startings[:-1],
#             endings,
#             overdrafts,
#         )
#
#
# class Interest:
#     amounts: rk.flux.Flow
#     balance: Balance
#
#     class Type(enum.Enum):
#         INTEREST_ONLY = "interest_only"
#         COMPOUND = "compound"
#         CAPITALIZED = "capitalized"
#
#     def __init__(
#         self,
#         rate: float | rk.flux.Flow,
#         transactions: rk.flux.Flow,
#         frequency: rk.duration.Type,
#         type: Type = Type.COMPOUND,
#     ):
#         """
#         Calculate interest expense on a loan or other interest-bearing liability,
#         described by a series of transactions.
#         Assumes interest is compounded on a positive, outstanding balance per period
#         (i.e. draws are positive, payments are negative).
#         Make sure the rate is consistent with the frequency.
#         """
#
#         transactions = transactions.resample(frequency=frequency)
#
#         if isinstance(rate, float):
#             rate = rk.flux.Flow.from_projection(
#                 name="Interest Rates",
#                 value=rate,
#                 proj=rk.projection.Extrapolation(
#                     form=rk.extrapolation.Recurring(),
#                     sequence=rk.duration.Sequence.from_datestamps(
#                         datestamps=transactions.movements.index, frequency=frequency
#                     ),
#                 ),
#             )
#         else:
#             raise NotImplementedError("Only float rates are supported currently.")
#
#         if len(transactions.movements) != len(rate.movements):
#             raise ValueError(
#                 "The number of transactions must match the number of rates."
#             )
#
#         startings, endings, amounts = self._calc_interest(
#             transactions=numba.typed.List(transactions.movements.to_list()),
#             rates=numba.typed.List(rate.movements.to_list()),
#             type=type.value,
#         )
#
#         startings = rk.flux.Flow(
#             movements=pd.Series(startings, index=transactions.movements.index),
#             units=transactions.units,
#         )
#         endings = rk.flux.Flow(
#             movements=pd.Series(endings, index=transactions.movements.index),
#             units=transactions.units,
#         )
#
#         self.balance = rk.formula.financial.Balance.from_flows(
#             startings=startings,
#             endings=endings,
#             frequency=frequency,
#         )
#
#         self.amounts = rk.flux.Flow(
#             movements=pd.Series(amounts, index=transactions.movements.index),
#             units=transactions.units,
#             name="Interest",
#         )
#
#     @staticmethod
#     @numba.jit
#     def _calc_interest(
#         transactions: numba.typed.List,
#         rates: numba.typed.List,
#         type: str,
#     ) -> (
#         numba.typed.List,
#         numba.typed.List,
#         numba.typed.List,
#     ):
#
#         startings = numba.typed.List.empty_list(numba.float64)
#         endings = numba.typed.List.empty_list(numba.float64)
#         amounts = numba.typed.List.empty_list(numba.float64)
#
#         for i in range(len(transactions)):
#             if i == 0:
#                 startings.append(0)
#             else:
#                 startings.append(endings[-1])
#
#             principal = startings[i] + transactions[i]
#             if type == "interest_only":
#                 interest = principal * rates[i] if principal > 0 else 0
#                 endings.append(principal)
#
#             elif type == "compound":
#                 interest = principal * rates[i] if principal > 0 else 0
#                 endings.append(principal + interest)
#
#             elif type == "capitalized":
#                 # Since we are capitalizing interest, the amount (draw) must include interest to pay on the principal.
#                 # Derived from i = r * (P + i)
#                 interest = (
#                     (principal * rates[i]) / (1 - rates[i]) if principal > 0 else 0
#                 )
#                 endings.append(principal + interest)
#
#             else:
#                 raise ValueError(f"Invalid instrument: {type}")
#
#             amounts.append(interest)
#
#         return (startings, endings, amounts)
