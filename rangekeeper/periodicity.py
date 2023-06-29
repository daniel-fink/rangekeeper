from __future__ import annotations

import math
from typing import Union, Optional

import aenum
import enum
from datetime import datetime
import dateutil.relativedelta
import pandas as pd

import rangekeeper as rk


class Type(enum.Enum):
    DECADE = '10A'
    SEMIDECADE = '5A'
    BIENNIUM = '2A'
    YEAR = 'A-DEC'  # Anchored on end of December
    SEMIYEAR = '6M'  # Anchored on end of June & December
    QUARTER = 'Q-DEC'  # Anchored on end of March, June, September, & December
    MONTH = 'M'  # Anchored on end-of-month
    SEMIMONTH = 'SM'  # Twice-monthly periods anchored on mid-month and end-of-month dates
    WEEK = 'W'  # Anchored on Sundays
    DAY = 'D'  # Daily


def from_value(value: str):
    if value == '10A':
        return Type.DECADE
    if value == '5A':
        return Type.SEMIDECADE
    if value == '2A':
        return Type.BIENNIUM
    if value == 'A-DEC':
        return Type.YEAR
    if value == '6M':
        return Type.SEMIYEAR
    if value == 'Q-DEC':
        return Type.QUARTER
    if value == 'M':
        return Type.MONTH
    if value == 'SM':
        return Type.SEMIMONTH
    if value == 'W':
        return Type.WEEK
    if value == 'D':
        return Type.DAY


def include_date(
        date: pd.Timestamp,
        duration: Type) -> pd.Period:
    """
    Returns a pd.Period that encompasses the given date
    """

    return pd.Period(year=date.year, month=date.month, day=date.day, freq=duration.value)


def period_index(
        include_start: pd.Timestamp,
        period_type: Type,
        bound: Union[pd.Timestamp, int] = None) -> pd.PeriodIndex:
    """
    Returns a pd.PeriodIndex from a start date with periods of given duration.
    Either an end date, or number of periods must be given to bound the sequence.

    :param include_start: pd.Timestamp start date
    :param period_type: Period frequency
    :param bound: A terminating condition; either a pd.Timestamp end date or a (integer) number of periods
    """
    if isinstance(bound, pd.Timestamp):
        return pd.period_range(
            start=include_start,
            end=bound,
            freq=period_type.value,
            name='periods')
    elif isinstance(bound, int):
        return pd.period_range(
            start=include_start,
            periods=bound,
            freq=period_type.value,
            name='periods')


def offset_periodindex(
        index: pd.PeriodIndex,
        offset_start: Optional[int] = None,
        offset_end: Optional[int] = None) -> pd.PeriodIndex:
    """
    Returns a pd.PeriodIndex with periods offset by given number of periods (of type given by the index)
    """
    start = index[0].to_timestamp()
    if offset_start is not None:
        start = offset_date(
            date=start,
            period_type=from_value(index.freq),
            num_periods=offset_start)
    end = index[-1].to_timestamp()
    if offset_end is not None:
        end = offset_date(
            date=index[-1].to_timestamp(),
            period_type=from_value(index.freq),
            num_periods=offset_end)
    return period_index(
        include_start=start,
        period_type=from_value(index.freq),
        bound=end)


def to_span(period_index: pd.PeriodIndex):
    """
    Returns a Span encompassing a pd.PeriodIndex
    """
    return rk.span.Span(
        start_date=period_index[0].to_timestamp(how='start'),
        end_date=period_index[-1].to_timestamp(how='end'))


def single_period_index(period: pd.Period) -> pd.PeriodIndex:
    return pd.period_range(
        start=period,
        periods=1)


def to_datestamps(
        period_index: pd.PeriodIndex,
        end: bool = True) -> pd.DatetimeIndex:
    """
    Returns a pd.DatetimeIndex from a pd.PeriodIndex with Datetimes being Dates
    :param end: If True, the end of the period is used. If False, the start of the period is used.
    """
    if end:
        timestamps = period_index.to_timestamp(how='end')
    else:
        timestamps = period_index.to_timestamp(how='start')
    datestamps = timestamps.date
    return pd.DatetimeIndex(datestamps)


def periods_per_year(period_type: Type) -> int:
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


def offset_date(
        date: pd.Timestamp,
        period_type: Type = Type.DAY,
        num_periods: int = 1) -> pd.Timestamp:
    """
    Offsets a date by a given number of periods
    :param date:
    :type date:
    :param period_type:
    :type period_type:
    :param num_periods:
    :type num_periods:
    :return:
    :rtype:
    """
    if period_type.value == Type.DECADE.value:
        return date + pd.DateOffset(years=10 * num_periods)
    elif period_type.value == Type.SEMIDECADE.value:
        return date + pd.DateOffset(years=5 * num_periods)
    elif period_type.value == Type.BIENNIUM.value:
        return date + pd.DateOffset(years=2 * num_periods)
    elif period_type.value == Type.YEAR.value:
        return date + pd.DateOffset(years=num_periods)
    elif period_type.value == Type.SEMIYEAR.value:
        return date + pd.DateOffset(months=6 * num_periods)
    elif period_type.value == Type.QUARTER.value:
        return date + pd.DateOffset(months=3 * num_periods)
    elif period_type.value == Type.MONTH.value:
        return date + pd.DateOffset(months=num_periods)
    elif period_type.value == Type.WEEK.value:
        return date + pd.DateOffset(weeks=num_periods)
    elif period_type.value == Type.DAY.value:
        return date + pd.DateOffset(days=num_periods)


def duration(
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        period_type: Type,
        inclusive: bool = False) -> int:
    """
    Returns the whole integer (i.e. no remainder) number of periods between
    given dates.
    If inclusive is True, the end_date is included in the calculation.
    """
    calc_end_date = end_date
    if inclusive:
        calc_end_date = offset_date(
            date=end_date,
            period_type=Type.DAY,
            num_periods=1)

    delta = dateutil.relativedelta.relativedelta(calc_end_date, start_date)

    if period_type.value == Type.DECADE.value:
        result = math.floor(delta.years / 10)
    elif period_type.value == Type.SEMIDECADE.value:
        result = math.floor(delta.years / 5)
    elif period_type.value == Type.BIENNIUM.value:
        result = math.floor(delta.years / 2)
    elif period_type.value == Type.YEAR.value:
        result = delta.years
    elif period_type.value == Type.SEMIYEAR.value:
        result = (delta.years * 2) + math.floor(delta.months / 6)
    elif period_type.value == Type.QUARTER.value:
        result = (delta.years * 4) + math.floor(delta.months / 3)
    elif period_type.value == Type.MONTH.value:
        result = (delta.years * 12) + delta.months
    elif period_type.value == Type.SEMIMONTH.value:
        result = (delta.years * 24) + delta.months * 2
    elif period_type.value == Type.WEEK.value:
        result = math.floor((calc_end_date - start_date).days / 7)
    elif period_type.value == Type.DAY.value:
        result = (calc_end_date - start_date).days
    else:
        raise ValueError('Unsupported period type: {0}'.format(period_type))

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


def to_range_index(
        period_index: pd.PeriodIndex,
        start_period: pd.Period = None,
        end_period: pd.Period = None) -> pd.RangeIndex:
    """
    Returns a RangeIndex that maps a PeriodIndex to a range of integers.
    """

    index_offset = None
    if start_period is None:
        start_period = period_index[0]
    if end_period is None:
        end_period = period_index[-1]
    bounds_index = pd.period_range(
        start=start_period,
        end=end_period,
        freq=period_index.freq)

    for i in range(bounds_index.size):
        if period_index.__contains__(bounds_index[i]):
            index_offset = i
            break
        else:
            continue
    return pd.RangeIndex(start=index_offset, stop=period_index.size + index_offset, step=1)
