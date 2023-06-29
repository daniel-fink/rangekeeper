from __future__ import annotations

import enum
import typing
from typing import Optional, Union, Tuple

import enum
import numpy as np
import pandas as pd
import scipy.stats as ss

import rangekeeper as rk


class Padding(enum.Enum):
    """
    Enum for padding types.
    """
    NIL = 'nil'  # Zero out factors or densities until bound
    UNITIZE = 'unitize'  # Repeat unit factor or density until bound
    EXTEND = 'extend'  # 'Repeat last factor or density until bound'


class Projection:
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
        if type == Padding.NIL:
            return np.zeros(shape=length)
        elif type == Padding.UNITIZE:
            return np.ones(shape=length)
        elif type == Padding.EXTEND:
            return np.full(shape=length, fill_value=value)
        elif type is None:
            return np.empty(shape=0)


class Extrapolation(Projection):
    form: rk.extrapolation.Form
    padding: Tuple[Optional[Padding], Optional[Padding]]

    def __init__(
            self,
            form: rk.extrapolation.Form,
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

    def terms(self) -> pd.Series:
        terms = self.form.terms(
            sequence=rk.periodicity.to_range_index(period_index=self.sequence))
        left_length = self.sequence[0] - self.bounds[0]
        right_length = self.bounds[1] - self.sequence[-1]
        left = self._pad(
            value=terms[0],
            length=left_length.n,
            type=self.padding[0])
        right = self._pad(
            value=terms[-1],
            length=right_length.n,
            type=self.padding[1])
        data = np.concatenate((left, terms, right))

        start = self.bounds[0].to_timestamp(how='start')
        bound = self.bounds[1].to_timestamp(how='end')

        period_index = rk.periodicity.period_index(
            include_start=start,
            period_type=rk.periodicity.from_value(self.sequence.freq),
            bound=bound)

        index = rk.periodicity.to_datestamps(period_index=period_index)

        result = pd.Series(
            data=data,
            index=index)

        # result = result[start:bound]

        return result

class Distribution(Projection):
    form: rk.distribution.Form

    def __init__(
            self,
            form: rk.distribution.Form,
            sequence: pd.PeriodIndex,
            bounds: Tuple[pd.Period, pd.Period] = None):
        super().__init__(
            sequence=sequence)
        self.form = form

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
            type=Padding.NIL)
        self._right_padding = self._pad(
            value=0,
            length=right_length.n,
            type=Padding.NIL)

        # self._index = periodicity.period_index(
        #     include_start=self.bounds[0].to_timestamp(),
        #     period_type=periodicity.from_value(self.sequence.freq),
        #     bound=self.bounds[1].to_timestamp())

    def _seq_to_params(self) -> [float]:
        range_index = rk.periodicity.to_range_index(
            period_index=self.sequence)
        range_index = range_index.insert(
            loc=len(range_index),
            item=range_index[-1] + 1)
        max = range_index[-1]
        return [index / max for index in range_index]

    def interval_density(self) -> pd.Series:
        densities = self.form.interval_density(parameters=self._parameters)
        data = np.concatenate((self._left_padding, densities, self._right_padding))

        return pd.Series(
            data=data,
            index=rk.periodicity.to_datestamps(
                rk.periodicity.period_index(
                    include_start=self.bounds[0].to_timestamp(),
                    period_type=rk.periodicity.from_value(self.sequence.freq),
                    bound=self.bounds[1].to_timestamp())))

    def cumulative_density(self) -> [float]:
        densities = self.form.cumulative_density(parameters=self._parameters)
        data = np.concatenate((self._left_padding, densities, self._right_padding))

        period_index = rk.periodicity.period_index(
            include_start=self.bounds[0].to_timestamp(),
            period_type=rk.periodicity.from_value(self.sequence.freq),
            bound=self.bounds[1].to_timestamp())
        datestamp_index = rk.periodicity.to_datestamps(period_index=period_index)
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
