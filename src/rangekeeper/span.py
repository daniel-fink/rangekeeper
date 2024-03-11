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
              amount: int,
              duration: rk.duration.Type,
              bound: str = 'end',
              name: str = None) -> Span:
        """
        Shift the Span's bounds by a specified period increment

        :param amount: The number of durations to shift the bounds
        :param duration: The duration type of the shift
        :param bound: The bound to shift. Options are 'start', 'end', or 'both'
        :param name: The name of the new Span, or the same name if None
        """
        name = self.name if name is None else name

        if bound == 'start':
            return Span(
                name=name,
                start_date=rk.duration.offset(
                    date=self.start_date,
                    duration=duration,
                    amount=amount),
                end_date=self.end_date)
        elif bound == 'end':
            return Span(
                name=name,
                start_date=self.start_date,
                end_date=rk.duration.offset(
                    date=self.end_date,
                    duration=duration,
                    amount=amount))
        elif bound == 'both':
            return Span(
                name=name,
                start_date=rk.duration.offset(
                    date=self.start_date,
                    duration=duration,
                    amount=amount),
                end_date=rk.duration.offset(
                    date=self.end_date,
                    duration=duration,
                    amount=amount))
        else:
            raise Exception('Error: invalid bound specified')

    def to_sequence(
            self,
            frequency: rk.duration.Type) -> pd.PeriodIndex:
        """
        Return a pd.PeriodIndex of the Span at the specified frequency
        """
        return rk.duration.Sequence.from_bounds(
            include_start=self.start_date,
            frequency=frequency,
            bound=self.end_date)

    def measure(
            self,
            duration: rk.duration.Type,
            inclusive: bool = False) -> int:
        """
        Return the whole-period duration of the Span in the specified period_type
        """
        return rk.duration.measure(
            start_date=self.start_date,
            end_date=self.end_date,
            duration=duration,
            inclusive=inclusive)

    @classmethod
    def from_duration(
            cls,
            name: str,
            date: pd.Timestamp,
            duration: rk.duration.Type,
            amount: int = 1) -> Span:
        """
        Create a Span from a date with a set number of periods of specified type.
        If the number of periods is negative, the Span will end on the date specified.
        If the number of periods is positive, the Span will start on the date specified.
        Defaults to 1 duration of the specified type.
        """
        if amount < 0:
            end_date = date
            start_date = rk.duration.offset(
                date=date,
                duration=duration,
                amount=amount)
            start_date = rk.duration.offset(
                date=start_date,
                duration=rk.duration.Type.DAY,
                amount=1)
            return cls(name=name, start_date=start_date, end_date=end_date)
        else:
            start_date = date
            end_date = rk.duration.offset(
                date=date,
                duration=duration,
                amount=amount)
            end_date = rk.duration.offset(
                date=end_date,
                duration=rk.duration.Type.DAY,
                amount=-1)
            return cls(name=name, start_date=start_date, end_date=end_date)

    @classmethod
    def from_dates(
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
        date_pairs = [(start, rk.duration.offset(end, rk.duration.Type.DAY, -1)) for (start, end) in
                      date_pairs]

        spans = []
        for i in range(len(names)):
            spans.append(cls(name=names[i], start_date=date_pairs[i][0], end_date=date_pairs[i][1]))
        return spans

    @classmethod
    def from_durations(
            cls,
            names: [str],
            duration: rk.duration.Type,
            amounts: [int],
            start_date: pd.Timestamp) -> [Span]:
        """
        Create a set of Spans from a sequence of durations of specified type
        """
        if len(names) != len(amounts):
            raise Exception('Error: number of Span names must equal number of Spans')

        dates = []
        cumulative_amounts = np.cumsum(amounts)
        for amount in cumulative_amounts:
            dates.append(rk.duration.offset(date=start_date, duration=duration, amount=amount))

        return cls.from_dates(names=names, dates=dates)
