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

        self.name = f"{name} Account"

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
                np.diff(overdraft, prepend=0),  # Cumulative -> Incremental
                index=transactions.movements.index,
            ),
            units=transactions.units,
            name=f"{name} Overdraft",
        )
        self.overdraft = overdraft.clean(zeroes=True)

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
        name = f"{self.name} (diff)" if name is None else name
        result = rk.flux.Flow(
            movements=self.endings.movements - self.startings.movements,
            units=self.startings.units,
            name=name,
        )
        return result.clean()
