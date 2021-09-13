import aenum
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
    def include_date(date: pd.Timestamp, duration: Type):
        """Returns a pd Period that encompasses the given date"""

        return pd.Period(year=date.year, month=date.month, day=date.day, freq=duration.value)

    @staticmethod
    def period_sequence(include_start: pd.Timestamp,
                        include_end: pd.Timestamp,
                        periodicity: Type):
        """Returns a pd.PeriodIndex that encompasses start & end dates with periods of given duration"""

        return pd.period_range(start=include_start, end=include_end, freq=periodicity.value)

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
            return date + pd.DateOffset(months=3*num_periods)
        elif period_type is Periodicity.Type.month:
            return date + pd.DateOffset(months=num_periods)
        elif period_type is Periodicity.Type.week:
            return date + pd.DateOffset(weeks=num_periods)
        elif period_type is Periodicity.Type.day:
            return date + pd.DateOffset(days=num_periods)

    @staticmethod
    def duration(start_date: pd.Timestamp,
                 end_date: pd.Timestamp,
                 period_type: Type):
        delta = start_date - end_date

        if period_type is Periodicity.Type.year:
            return delta / np.timedelta64(1, 'Y')
        if period_type is Periodicity.Type.quarter:
            return (delta / np.timedelta64(1, 'Y')) * 4
        if period_type is Periodicity.Type.month:
            return delta / np.timedelta64(1, 'M')
        if period_type is Periodicity.Type.semimonth:
            return (delta / np.timedelta64(1, 'M')) * 2
        if period_type is Periodicity.Type.week:
            return delta / np.timedelta64(1, 'W')
        if period_type is Periodicity.Type.day:
            return delta / np.timedelta64(1, 'D')

