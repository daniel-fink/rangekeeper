import math
from typing import Optional, Union
import aenum
import dateutil.relativedelta
import pandas as pd
import numpy as np


class Periodicity:
    class Type(aenum.Enum):
        _init_ = 'value __doc__'

        year = 'A-DEC', 'Anchored on end of December'
        quarter = 'Q-DEC', 'Anchored on end of March, June, September, & December'
        month = 'M', 'Anchored on end-of-month'
        semimonth = 'SM', 'Twice-monthly periods anchored on mid-month and end-of-month dates'
        week = 'W', 'Anchored on Sundays'
        day = 'D', 'Daily'

    @staticmethod
    def from_value(value: str):
        if value == 'A-DEC':
            return Periodicity.Type.year
        if value == 'Q-DEC':
            return Periodicity.Type.quarter
        if value == 'M':
            return Periodicity.Type.month
        if value == 'SM':
            return Periodicity.Type.semimonth
        if value == 'W':
            return Periodicity.Type.week
        if value == 'D':
            return Periodicity.Type.day

    @staticmethod
    def include_date(date: pd.Timestamp, duration: Type):
        """
        Returns a pd.Period that encompasses the given date
        """

        return pd.Period(year=date.year, month=date.month, day=date.day, freq=duration.value)

    @staticmethod
    def period_index(include_start: pd.Timestamp,
                     periodicity: Type,
                     bound: Union[pd.Timestamp, int] = None):
        """
        Returns a pd.PeriodIndex from a start date with periods of given duration.
        Either an end date, or number of periods must be given to bound the sequence.

        :param include_start: pd.Timestamp start date
        :param period_type: Period frequency
        :param bound: A terminating condition; either a pd.Timestamp end date or a (integer) number of periods
        """
        if isinstance(bound, pd.Timestamp):
            return pd.period_range(start=include_start,
                                   end=bound,
                                   freq=periodicity.value,
                                   name='periods')
        elif isinstance(bound, int):
            return pd.period_range(start=include_start,
                                   periods=bound,
                                   freq=periodicity.value,
                                   name='periods')

    @staticmethod
    def to_datestamps(period_index: pd.PeriodIndex):
        timestamps = period_index.to_timestamp(how='end')
        datestamps = timestamps.date
        return pd.DatetimeIndex(datestamps)

    @staticmethod
    def periods_per_year(period_type: Type):
        return {
            Periodicity.Type.year: 1,
            Periodicity.Type.quarter: 4,
            Periodicity.Type.month: 12,
            Periodicity.Type.semimonth: 24,
            Periodicity.Type.week: 52,
            Periodicity.Type.day: 365
            }.get(period_type, None)

    @staticmethod
    def date_offset(
            date: pd.Timestamp,
            period_type: Type,
            num_periods: int):
        if period_type is Periodicity.Type.year:
            return date + pd.DateOffset(years=num_periods)
        elif period_type is Periodicity.Type.quarter:
            return date + pd.DateOffset(months=3 * num_periods)
        elif period_type is Periodicity.Type.month:
            return date + pd.DateOffset(months=num_periods)
        elif period_type is Periodicity.Type.week:
            return date + pd.DateOffset(weeks=num_periods)
        elif period_type is Periodicity.Type.day:
            return date + pd.DateOffset(days=num_periods)

    @staticmethod
    def duration(start_date: pd.Timestamp,
                 end_date: pd.Timestamp,
                 period_type: Type,
                 inclusive: bool = False):
        """
        Returns the whole integer (i.e. no remainder)
        number of periods between given dates.
        If inclusive is True, the end_date is included in the calculation.
        """
        calc_end_date = end_date
        if inclusive:
            calc_end_date = Periodicity.date_offset(date=end_date,
                                                    period_type=Periodicity.Type.day,
                                                    num_periods=1)

        delta = dateutil.relativedelta.relativedelta(calc_end_date, start_date)

        if period_type is Periodicity.Type.year:
            return delta.years
        if period_type is Periodicity.Type.quarter:
            return (delta.years * 4) + math.floor(delta.months / 3)
        if period_type is Periodicity.Type.month:
            return (delta.years * 12) + delta.months
        if period_type is Periodicity.Type.semimonth:
            return (delta.years * 24) + delta.months * 2
        if period_type is Periodicity.Type.week:
            return math.floor((calc_end_date - start_date).days / 7)
        if period_type is Periodicity.Type.day:
            return (calc_end_date - start_date).days
