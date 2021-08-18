from aenum import Enum
import pandas as pd
import enum


class Periodicity:
    class Type(Enum):
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
        """Returns a pd PeriodIndex that encompasses start & end dates with periods of given duration"""

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
            number: int):
        if period_type is Periodicity.Type.year:
            return date + pd.DateOffset(years=number)
        elif period_type is Periodicity.Type.quarter:
            return date + pd.DateOffset(months=3*number)
        elif period_type is Periodicity.Type.month:
            return date + pd.DateOffset(months=number)
        elif period_type is Periodicity.Type.week:
            return date + pd.DateOffset(weeks=number)
        elif period_type is Periodicity.Type.day:
            return date + pd.DateOffset(days=number)



