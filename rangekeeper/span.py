from __future__ import annotations

import numpy as np
import pandas as pd

import rangekeeper as rk


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

    def shift(self,
              num_periods: int,
              period_type: rk.periodicity.Type,
              bound: str = 'end',
              name: str = None) -> Span:
        """
        Shift the Span's bounds by a specified period increment

        :param num_periods: The number of periods to shift the bounds
        :param period_type: The period type of the shift
        :param bound: The bound to shift. Options are 'start', 'end', or 'both'
        """
        name = self.name if name is None else name
        if bound == 'start':
            return Span(
                name=name,
                start_date=rk.periodicity.offset_date(
                    date=self.start_date,
                    period_type=period_type,
                    num_periods=num_periods),
                end_date=self.end_date)
        elif bound == 'end':
            return Span(
                name=name,
                start_date=self.start_date,
                end_date=rk.periodicity.offset_date(
                    date=self.end_date,
                    period_type=period_type,
                    num_periods=num_periods))
        elif bound == 'both':
            return Span(
                name=name,
                start_date=rk.periodicity.offset_date(
                    date=self.start_date,
                    period_type=period_type,
                    num_periods=num_periods),
                end_date=rk.periodicity.offset_date(
                    date=self.end_date,
                    period_type=period_type,
                    num_periods=num_periods))
        else:
            raise Exception('Error: invalid bound specified')

    def to_index(
            self,
            period_type: rk.periodicity.Type) -> pd.PeriodIndex:
        """
        Return a pd.PeriodIndex of the Span at the specified periodicity
        """
        return rk.periodicity.period_index(
            include_start=self.start_date,
            period_type=period_type,
            bound=self.end_date)

    def duration(
            self,
            period_type: rk.periodicity.Type,
            inclusive: bool = False) -> int:
        """
        Return the whole-period duration of the Span in the specified period_type
        """
        return rk.periodicity.duration(
            start_date=self.start_date,
            end_date=self.end_date,
            period_type=period_type,
            inclusive=inclusive)

    @classmethod
    def from_num_periods(
            cls,
            name: str,
            date: pd.Timestamp,
            period_type: rk.periodicity.Type,
            num_periods: int) -> Span:
        """
        Create a Span from a date with a set number of periods of specified type.
        If the number of periods is negative, the Span will end on the date specified.
        If the number of periods is positive, the Span will start on the date specified.
        """
        if num_periods < 0:
            end_date = date
            start_date = rk.periodicity.offset_date(
                date=date,
                period_type=period_type,
                num_periods=num_periods)
            start_date = rk.periodicity.offset_date(
                date=start_date,
                period_type=rk.periodicity.Type.DAY,
                num_periods=1)
            return cls(name=name, start_date=start_date, end_date=end_date)
        else:
            start_date = date
            end_date = rk.periodicity.offset_date(
                date=date,
                period_type=period_type,
                num_periods=num_periods)
            end_date = rk.periodicity.offset_date(
                date=end_date,
                period_type=rk.periodicity.Type.DAY,
                num_periods=-1)
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
        date_pairs = [(start, rk.periodicity.offset_date(end, rk.periodicity.Type.DAY, -1)) for (start, end) in
                      date_pairs]

        spans = []
        for i in range(len(names)):
            spans.append(cls(name=names[i], start_date=date_pairs[i][0], end_date=date_pairs[i][1]))
        return spans

    @classmethod
    def from_num_periods_sequence(
            cls,
            names: [str],
            period_type: rk.periodicity.Type,
            durations: [int],
            start_date: pd.Timestamp) -> [Span]:
        """
        Create a set of Spans from a sequence of durations of specified period type
        :param names:
        :type names:
        :param period_type:
        :type period_type:
        :param durations:
        :type durations:
        :param start_date:
        :type start_date:
        :return:
        :rtype:
        """
        if len(names) != len(durations):
            raise Exception('Error: number of Span names must equal number of Spans')

        dates = []
        cumulative_durations = np.cumsum(durations)
        for duration in cumulative_durations:
            dates.append(rk.periodicity.offset_date(date=start_date, period_type=period_type, num_periods=duration))

        return cls.from_date_sequence(names=names, dates=dates)
