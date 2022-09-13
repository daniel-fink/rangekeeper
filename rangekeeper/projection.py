from __future__ import annotations

import enum
import typing
from typing import Optional, Union, Tuple

import aenum
import numpy as np
import pandas as pd
import scipy.stats as ss
from abc import ABC, abstractmethod

from . import periodicity, distribution


class Padding(aenum.Enum):
    """
    Enum for padding types.
    """
    _init_ = 'value', '__doc__'

    nil = 'nil', 'Zero out factors or densities until bound'
    unitize = 'unitize', 'Repeat unit factor or density until bound'
    extend = 'extend', 'Repeat last factor or density until bound'


class Projection(ABC):
    sequence: pd.PeriodIndex
    bounds: Tuple[pd.Period, pd.Period]

    def __init__(
            self,
            sequence: pd.PeriodIndex,
            bounds: Tuple[pd.Period, pd.Period] = None):
        self.sequence = sequence

        if bounds is None:
            self.bounds = (sequence[0], sequence[-1])
        else:
            self.bounds = bounds

    # def __init__(
    #         self,
    #         sequence: Union[pd.RangeIndex, pd.PeriodIndex],
    #         bounds: Union[Tuple[int, int], Tuple[pd.Period, pd.Period]] = None):
    #
    #     if isinstance(sequence, pd.RangeIndex):
    #         if bounds is None:
    #             self.sequence = sequence
    #             self.bounds = (0, len(sequence))
    #         elif isinstance(bounds[0], int):
    #             self.sequence = sequence
    #             self.bounds = bounds
    #         else:
    #             raise ValueError(f"sequence and bounds must match in type (int or pd.Period)")
    #
    #     elif isinstance(sequence, pd.PeriodIndex):
    #         if bounds is None:
    #             self.sequence = periodicity.to_range_index(
    #                 period_index=sequence)
    #             self.bounds = (0, len(sequence))
    #         elif isinstance(bounds[0], pd.Period):
    #             self.sequence = periodicity.to_range_index(
    #                 period_index=sequence,
    #                 start=bounds[0],
    #                 end=bounds[1])
    #             bounds_range = pd.period_range(
    #                 start=bounds[0],
    #                 end=bounds[1],
    #                 freq=sequence.freq)
    #             self.bounds = (0, len(bounds_range))
    #         else:
    #             raise ValueError(f"sequence and bounds must match in type (int or pd.Period)")
    #
    #     else:
    #         raise ValueError(f"sequence must be of type (pd.RangeIndex or pd.PeriodIndex)")

    @staticmethod
    def _pad(
            value: float,
            length: int,
            type: Optional[Padding]) -> np.ndarray:
        if type == Padding.nil:
            return np.zeros(shape=length)
        elif type == Padding.unitize:
            return np.ones(shape=length)
        elif type == Padding.extend:
            return np.full(shape=length, fill_value=value)
        elif type is None:
            return np.empty(shape=0)


class Extrapolation(Projection):
    form: Form
    padding: Tuple[Padding, Padding]

    def __init__(
            self,
            form: Form,
            sequence: pd.PeriodIndex,
            bounds: Tuple[pd.Period, pd.Period] = None,
            padding: Tuple[Padding, Padding] = None):
        super().__init__(
            sequence=sequence,
            bounds=bounds)
        self.form = form

        if padding is None:
            if self.bounds[0] == sequence[0] and self.bounds[1] == sequence[-1]:
                self.padding = (None, None)
            else:
                raise ValueError('Error: Since the bounds do not match sequence start & end,'
                                 ' padding must be specified.')
        else:
            self.padding = padding

    def factors(self) -> pd.Series:
        factors = self.form.factors(
            periodicity.to_range_index(
                period_index=self.sequence))
        left_length = self.sequence[0] - self.bounds[0]
        right_length = self.bounds[1] - self.sequence[-1]
        left = self._pad(
            value=factors[0],
            length=left_length.n,
            type=self.padding[0])
        right = self._pad(
            value=factors[-1],
            length=right_length.n,
            type=self.padding[1])
        data = np.concatenate((left, factors, right))

        return pd.Series(
            data=data,
            index=periodicity.to_datestamps(
                periodicity.period_index(
                    include_start=self.bounds[0].to_timestamp(),
                    period_type=periodicity.from_value(self.sequence.freq),
                    bound=self.bounds[1].to_timestamp())))

    class Form:
        """
        A specified methodology, logic, or algorithm for extrapolating a value to a sequence.
        """

        @abstractmethod
        def factors(
                self,
                sequence: pd.RangeIndex) -> [float]:
            """
            Returns the multiplicative factor of the projection's form at each value in the sequence.
            """
            pass

    class StraightLine(Form):
        """
        A constant-change (linearly growing (or decaying)) projection form, originating from an initial value.
        To calculate the factor, the projection is modelled as a linear function of (slope * period) + 1
        """
        slope: float

        def __init__(
                self,
                slope: float):
            self.slope = slope

        def factors(
                self,
                sequence: pd.RangeIndex) -> [float]:
            """
            Returns the multiplicative factor of the projection at each value in the sequence.
            """
            return [(self.slope * index) + 1 for index in sequence]

    class Recurring(StraightLine):
        def __init__(self):
            super().__init__(slope=0)

    class Compounding(Form):
        """
        An exponentially growing (compounding) or decaying projection at a specified rate per period.
        To calculate the factor, the projection is modelled as an exponential function of (1 + rate) ** period
        """
        rate: float

        def __init__(
                self,
                rate: float):
            self.rate = rate

        def factors(
                self,
                sequence: pd.RangeIndex) -> [float]:
            """
            Returns the multiplicative factor of the projection's form at each value in the sequence.
            """
            return [np.power((1 + self.rate), index) for index in sequence]


class Distribution(Projection):
    dist: distribution.Form

    def __init__(
            self,
            dist: distribution.Form,
            sequence: pd.PeriodIndex,
            bounds: Tuple[pd.Period, pd.Period] = None):
        super().__init__(
            sequence=sequence)
        self.dist = dist

        if bounds is None:
            self.bounds = (sequence[0], sequence[-1])
        elif (bounds[0] > sequence[0]) or (bounds[1] < sequence[-1]):
            raise ValueError('Error: Bounds cannot be within the sequence for '
                             'Distribution Projections')
        else:
            self.bounds = bounds

        self._parameters = self._seq_to_params()

        left_length = self.sequence[0] - self.bounds[0]
        right_length = self.bounds[1] - self.sequence[-1]
        self._left_padding = self._pad(
            value=0,
            length=left_length.n,
            type=Padding.nil)
        self._right_padding = self._pad(
            value=0,
            length=right_length.n,
            type=Padding.nil)

        # self._index = periodicity.period_index(
        #     include_start=self.bounds[0].to_timestamp(),
        #     period_type=periodicity.from_value(self.sequence.freq),
        #     bound=self.bounds[1].to_timestamp())

    def _seq_to_params(self) -> [float]:
        range_index = periodicity.to_range_index(
            period_index=self.sequence)
        range_index = range_index.insert(
            loc=len(range_index),
            item=range_index[-1] + 1)
        max = range_index[-1]
        return [index / max for index in range_index]

    def interval_density(self) -> pd.Series:
        densities = self.dist.interval_density(parameters=self._parameters)
        data = np.concatenate((self._left_padding, densities, self._right_padding))

        return pd.Series(
            data=data,
            index=periodicity.to_datestamps(
                periodicity.period_index(
                    include_start=self.bounds[0].to_timestamp(),
                    period_type=periodicity.from_value(self.sequence.freq),
                    bound=self.bounds[1].to_timestamp())))

    def cumulative_density(self) -> [float]:
        densities = self.dist.cumulative_density(parameters=self._parameters)
        data = np.concatenate((self._left_padding, densities, self._right_padding))

        period_index = periodicity.period_index(
            include_start=self.bounds[0].to_timestamp(),
            period_type=periodicity.from_value(self.sequence.freq),
            bound=self.bounds[1].to_timestamp())
        datestamp_index = periodicity.to_datestamps(period_index=period_index)
        datestamp_index = datestamp_index.insert(loc=0, item=self.bounds[0].start_time)

        return pd.Series(
            data=data,
            index=datestamp_index)

# class DistributiveInterpolation(Interpolation):
#     """
#     A projection that apportions values over a range, according to a specified
#     distribution type.
#     """
#     dist: distribution.Form
#
#     def __init__(
#             self,
#             dist: distribution.Form,
#             sequence: Union[pd.RangeIndex, pd.PeriodIndex],
#             bounds: Union[Tuple[int, int], Tuple[pd.Period, pd.Period]]):
#         super().__init__(
#             sequence=sequence,
#             bounds=bounds)
#         self.dist = dist

# def map(
#         self,
#         left_padding: Padding = None,
#         right_padding: Padding = None) -> pd.Series:


# if isinstance(self.sequence, pd.RangeIndex):
#     if isinstance(self, Extrapolation):
#         factors = self.factor()
#         left = self.pad(
#             value=factors[0],
#             length=self.sequence[0] - self.bounds[0],
#             type=left_padding)
#         right = self.pad(
#             value=factors[-1],
#             length=self.bounds[1] - self.sequence[-1],
#             type=right_padding)
#         return pd.Series(
#             data=np.concatenate((left, factors, right)),
#             index=range(self.bounds[0], self.bounds[1]))
