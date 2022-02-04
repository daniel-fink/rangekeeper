from __future__ import annotations

import numpy as np
import pandas as pd

from periodicity import Periodicity


class Phase:
    name: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    """
    A `Phase` is a pd.Interval of pd.Timestamps that bound its start and end dates
    """

    def __init__(
            self,
            name: str,
            start_date: pd.Timestamp,
            end_date: pd.Timestamp):
        if end_date < start_date:
            raise Exception('Error: end_date cannot be before start_date')
        self.name = name

        self._interval = pd.Interval(left=start_date, right=end_date)
        self.start_date = self._interval.left
        self.end_date = self._interval.right

    def __str__(self):
        return 'Phase: {}\n' \
               'Start Date: {}\n' \
               'End Date: {}'.format(self.name, self.start_date, self.end_date)

    @classmethod
    def merge(
            cls,
            name: str,
            phases: [Phase]) -> Phase:
        """
        Merge a set of Phases into a single Phase
        """
        start_date = phases[0].start_date
        end_date = phases[0].end_date
        for phase in phases:
            if phase.start_date < start_date:
                start_date = phase.start_date
            if phase.end_date > end_date:
                end_date = phase.end_date
        return cls(name=name,
                   start_date=start_date,
                   end_date=end_date)

    def to_index(
            self,
            periodicity: Periodicity.Type) -> pd.PeriodIndex:
        """
        Return a pd.PeriodIndex of the Phase at the specified periodicity
        """
        return Periodicity.period_index(
            include_start=self.start_date,
            periodicity=periodicity,
            bound=self.end_date)

    def duration(
            self,
            period_type: Periodicity.Type,
            inclusive: bool = False) -> int:
        """
        Return the duration of the Phase in the specified period_type
        :param period_type:
        :type period_type:
        :param inclusive:
        :type inclusive:
        :return:
        :rtype:
        """
        return Periodicity.duration(start_date=self.start_date,
                                    end_date=self.end_date,
                                    period_type=period_type,
                                    inclusive=inclusive)

    @classmethod
    def from_num_periods(
            cls,
            name: str,
            start_date: pd.Timestamp,
            period_type: Periodicity.Type,
            num_periods: int) -> Phase:
        """
        Create a Phase from a start_date with a set number of periods of specified type.
        """
        if num_periods < 0:
            raise Exception('Error: Number of periods must be greater than 0')
        else:
            end_date = Periodicity.date_offset(
                date=start_date,
                period_type=period_type,
                num_periods=num_periods)
            end_date = Periodicity.date_offset(
                date=end_date,
                period_type=Periodicity.Type.day,
                num_periods=-1)
            return cls(name=name, start_date=start_date, end_date=end_date)

    @classmethod
    def from_date_sequence(
            cls,
            names: [str],
            dates: [pd.Timestamp]) -> [Phase]:
        """
        Create a set of Phases from a sequence of dates.
        Note: dates list length must be 1 longer than names
        :param names:
        :type names:
        :param dates:
        :type dates:
        :return:
        :rtype:
        """
        if len(names) != len(dates) - 1:
            raise Exception('Error: number of Phase names must equal number of Phases created'
                            ' (i.e. one less than number of dates)')

        date_pairs = list(zip(dates, dates[1:]))
        date_pairs = [(start, Periodicity.date_offset(end, Periodicity.Type.day, -1)) for (start, end) in date_pairs]

        phases = []
        for i in range(len(names)):
            phases.append(cls(name=names[i], start_date=date_pairs[i][0], end_date=date_pairs[i][1]))
        return phases

    @classmethod
    def from_num_periods_sequence(
            cls,
            names: [str],
            period_type: Periodicity.Type,
            durations: [int],
            start_date: pd.Timestamp) -> [Phase]:
        """
        Create a set of Phases from a sequence of durations of specified period type
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
            raise Exception('Error: number of Phase names must equal number of Phases')

        dates = []
        cumulative_durations = np.cumsum(durations)
        for duration in cumulative_durations:
            dates.append(Periodicity.date_offset(date=start_date, period_type=period_type, num_periods=duration))

        return cls.from_date_sequence(names=names, dates=dates)
