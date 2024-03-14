from __future__ import annotations

import enum
import math
from datetime import datetime
import dateutil
from typing import Union, Optional

import numpy as np
import pandas as pd


class Type(enum.Enum):
    DECADE = '10YE'
    SEMIDECADE = '5YE'
    BIENNIUM = '2YE'
    YEAR = 'YE'
    SEMIYEAR = '6ME'
    QUARTER = 'QE'
    MONTH = 'ME'
    SEMIMONTH = 'SME'
    WEEK = 'W'
    DAY = 'D'

    @staticmethod
    def from_value(value: str):
        if value == '10YE':
            return Type.DECADE
        if value == '5YE':
            return Type.SEMIDECADE
        if value == '2YE':
            return Type.BIENNIUM
        if value == 'YE':
            return Type.YEAR
        if value == '6ME':
            return Type.SEMIYEAR
        if value == 'QE':
            return Type.QUARTER
        if value == 'ME':
            return Type.MONTH
        if value == 'SME':
            return Type.SEMIMONTH
        if value == 'W':
            return Type.WEEK
        if value == 'D':
            return Type.DAY

    @staticmethod
    def period(type: Type):
        if type == Type.DECADE:
            return '10Y'
        if type == Type.SEMIDECADE:
            return '5Y'
        if type == Type.BIENNIUM:
            return '2Y'
        if type == Type.YEAR:
            return 'Y'
        if type == Type.SEMIYEAR:
            return '6M'
        if type == Type.QUARTER:
            return 'Q'
        if type == Type.MONTH:
            return 'M'
        if type == Type.SEMIMONTH:
            return 'SM'
        if type == Type.WEEK:
            return 'W'
        if type == Type.DAY:
            return 'D'


def measure(
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        duration: Type,
        inclusive: bool = False) -> int:
    """
    Returns the whole integer (i.e. no remainder) number of periods between
    given dates.
    If inclusive is True, the end_date is included in the calculation.
    """
    calc_end_date = end_date
    if inclusive:
        calc_end_date = offset(
            date=end_date,
            duration=Type.DAY,
            amount=1)

    delta = dateutil.relativedelta.relativedelta(calc_end_date, start_date)

    if duration.value == Type.DECADE.value:
        result = math.floor(delta.years / 10)
    elif duration.value == Type.SEMIDECADE.value:
        result = math.floor(delta.years / 5)
    elif duration.value == Type.BIENNIUM.value:
        result = math.floor(delta.years / 2)
    elif duration.value == Type.YEAR.value:
        result = delta.years
    elif duration.value == Type.SEMIYEAR.value:
        result = (delta.years * 2) + math.floor(delta.months / 6)
    elif duration.value == Type.QUARTER.value:
        result = (delta.years * 4) + math.floor(delta.months / 3)
    elif duration.value == Type.MONTH.value:
        result = (delta.years * 12) + delta.months
    elif duration.value == Type.SEMIMONTH.value:
        result = (delta.years * 24) + delta.months * 2
    elif duration.value == Type.WEEK.value:
        result = math.floor((calc_end_date - start_date).days / 7)
    elif duration.value == Type.DAY.value:
        result = (calc_end_date - start_date).days
    else:
        raise ValueError('Unsupported period type: {0}'.format(duration))

    def direction(rd: dateutil.relativedelta.relativedelta) -> int:
        """
        Check whether a relativedelta object is negative
        From https://stackoverflow.com/a/57906103/10964780
        """
        try:
            datetime.min + rd
            return 1
        except OverflowError:
            return -1

    return result * direction(delta)


def offset(
        date: pd.Timestamp,
        duration: Type = Type.DAY,
        amount: int = 1) -> pd.Timestamp:
    """
    Offsets a date by an amount of durations
    """
    if duration.value == Type.DECADE.value:
        return date + pd.DateOffset(years=10 * amount)
    elif duration.value == Type.SEMIDECADE.value:
        return date + pd.DateOffset(years=5 * amount)
    elif duration.value == Type.BIENNIUM.value:
        return date + pd.DateOffset(years=2 * amount)
    elif duration.value == Type.YEAR.value:
        return date + pd.DateOffset(years=amount)
    elif duration.value == Type.SEMIYEAR.value:
        return date + pd.DateOffset(months=6 * amount)
    elif duration.value == Type.QUARTER.value:
        return date + pd.DateOffset(months=3 * amount)
    elif duration.value == Type.MONTH.value:
        return date + pd.DateOffset(months=amount)
    elif duration.value == Type.WEEK.value:
        return date + pd.DateOffset(weeks=amount)
    elif duration.value == Type.DAY.value:
        return date + pd.DateOffset(days=amount)


class Period:
    @staticmethod
    def include_date(
            date: pd.Timestamp,
            duration: Type) -> pd.Period:
        """
        Returns a pd.Period that encompasses the given date
        """
        return pd.Period(year=date.year, month=date.month, day=date.day, freq=Type.period(duration))

    @staticmethod
    def to_sequence(period: pd.Period) -> pd.PeriodIndex:
        """
        Returns a single-period pd.PeriodIndex of a pd.Period
        """
        return pd.period_range(
            start=period,
            periods=1)

    @staticmethod
    def yearly_count(period_type: Type) -> int:
        """
        Returns the number of periods in a year of the given type
        """
        return {
            Type.DECADE: 0.1,
            Type.SEMIDECADE: 0.2,
            Type.BIENNIUM: 0.5,
            Type.YEAR: 1,
            Type.SEMIYEAR: 2,
            Type.QUARTER: 4,
            Type.MONTH: 12,
            Type.SEMIMONTH: 24,
            Type.WEEK: 52,
            Type.DAY: 365
            }.get(period_type, None)


class Sequence:
    @staticmethod
    def from_bounds(
            include_start: pd.Timestamp,
            frequency: Type,
            bound: Union[pd.Timestamp, int]) -> pd.PeriodIndex:
        """
        Returns a pd.PeriodIndex from a start date with periods of given duration.
        Either an end date, or number of periods must be given to bound the sequence.

        :param include_start: pd.Timestamp start date
        :param frequency: Index frequency
        :param bound: A terminating condition; either a pd.Timestamp end date or a (integer) number of periods
        """
        if isinstance(bound, pd.Timestamp):
            return pd.period_range(
                start=include_start,
                end=bound,
                freq=Type.period(frequency),
                name='periods')
        elif isinstance(bound, int):
            return pd.period_range(
                start=include_start,
                periods=bound,
                freq=Type.period(frequency),
                name='periods')

    @staticmethod
    def to_datestamps(
            sequence: pd.PeriodIndex,
            end: bool = True) -> pd.DatetimeIndex:
        """
        Returns a pd.DatetimeIndex from a pd.PeriodIndex with Datetimes being Dates
        :param sequence: pd.PeriodIndex
        :param end: If True, the end of the period is used. If False, the start of the period is used.
        """
        if end:
            timestamps = sequence.to_timestamp(how='end')
        else:
            timestamps = sequence.to_timestamp(how='start')
        datestamps = timestamps.date
        return pd.DatetimeIndex(datestamps)

    @staticmethod
    def extend(
            sequence: pd.PeriodIndex,
            start_offset: Optional[int] = None,
            end_offset: Optional[int] = None) -> pd.PeriodIndex:
        """
        Returns a pd.PeriodIndex with periods extended by given number of periods (of type given by the index)
        """
        start = sequence[0].to_timestamp()
        if start_offset is not None:
            start = offset(
                date=start,
                duration=Type.from_value(sequence.freq),
                amount=start_offset)

        end = sequence[-1].to_timestamp()
        if end_offset is not None:
            end = offset(
                date=sequence[-1].to_timestamp(),
                duration=Type.from_value(sequence.freq),
                amount=end_offset)

        return Sequence.from_bounds(
            include_start=start,
            frequency=Type.from_value(sequence.freq),
            bound=end)

    @staticmethod
    def to_range_index(
            sequence: pd.PeriodIndex,
            start_period: pd.Period = None,
            end_period: pd.Period = None) -> pd.RangeIndex:
        """
        Returns a RangeIndex that maps a PeriodIndex to a range of integers.
        """

        index_offset = None
        if start_period is None:
            start_period = sequence[0]
        if end_period is None:
            end_period = sequence[-1]
        bounds_index = pd.period_range(
            start=start_period,
            end=end_period,
            freq=sequence.freq)

        for i in range(bounds_index.size):
            if sequence.__contains__(bounds_index[i]):
                index_offset = i
                break
            else:
                continue
        return pd.RangeIndex(start=index_offset, stop=sequence.size + index_offset, step=1)


class Span:
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    name: str = None
    """
    A `Span` is a pd.Interval of pd.Timestamps that bound its start and end dates
    """

    def __init__(
            self,
            start_date: pd.Timestamp,
            end_date: pd.Timestamp = None,
            name: str = None):
        """
        Define a Span using dates and a name. If no end date is provided, it is
        assumed to be a one-day Span (ie, the start and end dates are the same)
        :param start_date:
        :param end_date:
        :param name:
        """
        if end_date is None:
            end_date = start_date
        elif end_date < start_date:
            raise Exception('Error: end_date cannot be before start_date')

        if name is None:
            self.name = ''
        else:
            self.name = name

        self._interval = pd.Interval(left=start_date, right=end_date)
        self.start_date = self._interval.left
        self.end_date = self._interval.right

    def __str__(self):
        return 'Span: {}\n' \
               'Start Date: {}\n' \
               'End Date: {}'.format(self.name, self.start_date.date(), self.end_date.date())

    def __repr__(self):
        return self.__str__()

    @classmethod
    def merge(
            cls,
            name: str,
            spans: [Span]) -> Span:
        """
        Merge a set of Spans into a single Span
        """
        start_date = spans[0].start_date
        end_date = spans[0].end_date
        for span in spans:
            if span.start_date < start_date:
                start_date = span.start_date
            if span.end_date > end_date:
                end_date = span.end_date
        return cls(name=name,
                   start_date=start_date,
                   end_date=end_date)

    def extend(
            self,
            duration: Type,
            amount: int,
            bound: str = 'end',
            name: str = None) -> Span:
        """
        Extend the Span's bounds by a specified period increment

        :param duration: The period type to extend by
        :param amount: The number of periods to extend the bounds
        :param bound: The bound to extend. Options are 'start', 'end', or 'both'
        :param name: The name of the new Span (or the same if None)
        """
        name = self.name if name is None else name
        start_date = offset(
            date=self.start_date,
            duration=duration,
            amount=amount)
        end_date = offset(
            date=self.end_date,
            duration=duration,
            amount=amount)

        if bound == 'start':
            return Span(
                name=name,
                start_date=start_date,
                end_date=self.end_date)
        elif bound == 'end':
            return Span(
                name=name,
                start_date=self.start_date,
                end_date=end_date)
        elif bound == 'both':
            return Span(
                name=name,
                start_date=start_date,
                end_date=end_date)
        else:
            raise Exception('Error: invalid bound specified')

    def to_sequence(
            self,
            frequency: Type) -> pd.PeriodIndex:
        """
        Return a pd.PeriodIndex of the Span at the specified frequency
        """
        return Sequence.from_bounds(
            include_start=self.start_date,
            frequency=frequency,
            bound=self.end_date)

    def duration(
            self,
            period_type: Type,
            inclusive: bool = False) -> int:
        """
        Return the whole-period duration of the Span of the specified period type
        """
        return measure(
            start_date=self.start_date,
            end_date=self.end_date,
            period_type=period_type,
            inclusive=inclusive)

    @classmethod
    def from_duration(
            cls,
            name: str,
            date: pd.Timestamp,
            duration: Type,
            amount: int = 1) -> Span:
        """
        Create a Span from a date with a set number of periods of specified type.
        If the number of periods is negative, the Span will end on the date specified.
        If the number of periods is positive, the Span will start on the date specified.
        """
        if amount < 0:
            end_date = date
            start_date = offset(
                date=date,
                duration=duration,
                amount=amount)
            start_date = offset(
                date=start_date,
                duration=Type.DAY,
                amount=1)
            return cls(name=name, start_date=start_date, end_date=end_date)
        else:
            start_date = date
            end_date = offset(
                date=date,
                duration=duration,
                amount=amount)
            end_date = offset(
                date=end_date,
                duration=Type.DAY,
                amount=-1)
            return cls(name=name, start_date=start_date, end_date=end_date)

    @classmethod
    def from_date_sequence(
            cls,
            names: [str],
            dates: [pd.Timestamp]) -> [Span]:
        """
        Create a set of Spans from a sequence of dates.
        Note: dates list length must be 1 longer than names
        :param names:
        :type names:
        :param dates:
        :type dates:
        :return:
        :rtype:
        """
        if len(names) != len(dates) - 1:
            raise Exception('Error: number of Span names must equal number of Spans created'
                            ' (i.e. one less than number of dates)')

        date_pairs = list(zip(dates, dates[1:]))
        date_pairs = [(start, offset(end, Type.DAY, -1)) for (start, end) in
                      date_pairs]

        spans = []
        for i in range(len(names)):
            spans.append(cls(name=names[i], start_date=date_pairs[i][0], end_date=date_pairs[i][1]))
        return spans

    @classmethod
    def from_duration_sequence(
            cls,
            duration: Type,
            names: [str],
            amounts: [int],
            start_date: pd.Timestamp) -> [Span]:
        """
        Create a set of Spans from a sequence of durations of specified period type
        """
        if len(names) != len(amounts):
            raise Exception('Error: number of Span names must equal number of Spans')

        dates = []
        cumulative_amounts = np.cumsum(amounts)
        for amount in cumulative_amounts:
            dates.append(offset(date=start_date, duration=duration, amount=amount))

        return cls.from_date_sequence(names=names, dates=dates)

    @classmethod
    def from_sequence(
            cls,
            sequence: pd.PeriodIndex):
        """
        Returns a Span encompassing a pd.PeriodIndex
        """
        return cls(
            start_date=sequence[0].to_timestamp(how='start'),
            end_date=sequence[-1].to_timestamp(how='end'))
