"""Independent calendar grids, anchor rules and current Period boundaries."""

from datetime import date, datetime
import pytest

from rangekeeper.model.duration import (
    Frequency,
    MonthRoll,
    PeriodTiming,
    offset,
    measure,
    align,
    make_periods,
    periods_between,
    make_period,
)
from rangekeeper.model.duration import Period, Span
from rangekeeper.model.flow import Flow


def test_month_rules_keep_the_original_anchor():
    assert offset(date(2026, 4, 30), frequency=Frequency.MONTH) == date(2026, 5, 31)
    assert offset(
        date(2026, 4, 30), frequency=Frequency.MONTH, month_roll=MonthRoll.CLAMP
    ) == date(2026, 5, 30)
    for day, march in ((30, 30), (31, 31)):
        periods = make_periods(date(2026, 1, day), frequency=Frequency.MONTH, count=2)
        assert [p.end for p in periods] == [date(2026, 2, 28), date(2026, 3, march)]
        assert periods[0].first == date(2026, 1, day)
    assert offset(date(2026, 1, 15), frequency=Frequency.MONTH, count=0) == date(
        2026, 1, 15
    )
    assert offset(date(2026, 4, 30), frequency=Frequency.WEEK) == date(2026, 5, 7)


@pytest.mark.parametrize(
    "frequency,expected",
    [
        (Frequency.DAY, (date(2026, 8, 20), date(2026, 8, 21))),
        (Frequency.WEEK, (date(2026, 8, 17), date(2026, 8, 24))),
        (Frequency.MONTH, (date(2026, 8, 1), date(2026, 9, 1))),
        (Frequency.QUARTER, (date(2026, 7, 1), date(2026, 10, 1))),
        (Frequency.HALFYEAR, (date(2026, 7, 1), date(2027, 1, 1))),
        (Frequency.YEAR, (date(2026, 1, 1), date(2027, 1, 1))),
    ],
)
def test_calendar_containing_period(frequency, expected):
    result = align(date(2026, 8, 20), frequency=frequency)
    assert (result.first, result.end) == expected


def test_fiscal_alignment_and_explicit_month_end_selection():
    year = align(date(2026, 3, 3), frequency=Frequency.YEAR, year_start_month=7)
    assert (year.first, year.end) == (date(2025, 7, 1), date(2026, 7, 1))
    half = align(date(2026, 3, 3), frequency=Frequency.HALFYEAR, year_start_month=7)
    assert (half.first, half.end) == (date(2026, 1, 1), date(2026, 7, 1))
    anchor = align(date(2026, 1, 15), frequency=Frequency.MONTH).resolve(
        timing=PeriodTiming.LAST
    )
    assert anchor == date(2026, 1, 31)
    assert make_periods(anchor, frequency=Frequency.MONTH, count=1)[0].end == date(
        2026, 2, 28
    )


def test_fortnight_origins_define_opposite_continuous_grids():
    first = align(
        date(2026, 1, 12), frequency=Frequency.BIWEEK, origin=date(2026, 1, 5)
    )
    second = align(
        date(2026, 1, 12), frequency=Frequency.BIWEEK, origin=date(2026, 1, 12)
    )
    assert (first.first, first.end) == (date(2026, 1, 5), date(2026, 1, 19))
    assert (second.first, second.end) == (date(2026, 1, 12), date(2026, 1, 26))
    before = align(
        date(2025, 12, 31), frequency=Frequency.BIWEEK, origin=date(2026, 1, 5)
    )
    assert (before.first, before.end) == (date(2025, 12, 22), date(2026, 1, 5))
    with pytest.raises(ValueError, match="origin"):
        align(date(2026, 1, 1), frequency=Frequency.BIWEEK)
    with pytest.raises(ValueError, match="conflicts"):
        align(date(2026, 1, 1), frequency=Frequency.BIWEEK, origin=date(2026, 1, 6))


@pytest.mark.parametrize(
    "frequency,first,end",
    [
        (Frequency.BIENNIUM, date(2025, 7, 1), date(2027, 7, 1)),
        (Frequency.QUINQUENNIUM, date(2026, 7, 1), date(2031, 7, 1)),
        (Frequency.DECADE, date(2021, 7, 1), date(2031, 7, 1)),
    ],
)
def test_multiyear_origins_and_exclusive_boundaries(frequency, first, end):
    p = align(
        date(2026, 8, 1),
        frequency=frequency,
        origin=date(2021, 7, 1),
        year_start_month=7,
    )
    assert (p.first, p.end) == (first, end)
    assert (
        align(
            p.end, frequency=frequency, origin=date(2021, 7, 1), year_start_month=7
        ).first
        == end
    )
    with pytest.raises(ValueError, match="origin"):
        align(date(2026, 8, 1), frequency=frequency)
    with pytest.raises(ValueError, match="conflicts"):
        align(date(2026, 8, 1), frequency=frequency, origin=date(2021, 7, 1))


def test_complete_step_measurement_is_sign_symmetric():
    a, b = date(2026, 1, 30), date(2026, 3, 29)
    assert measure(a, b, frequency=Frequency.MONTH) == 1
    assert measure(b, a, frequency=Frequency.MONTH) == -1
    assert measure(a, date(2026, 3, 30), frequency=Frequency.MONTH) == 2
    assert measure(a, a, frequency=Frequency.MONTH) == 0
    assert measure(date(2026, 1, 1), date(2026, 1, 14), frequency=Frequency.BIWEEK) == 0
    # Clamping a signed offset is deliberately not always inverted by measurement.
    later = date(2026, 3, 30)
    earlier = offset(later, frequency=Frequency.MONTH, count=-1)
    assert earlier == date(2026, 2, 28)
    assert measure(later, earlier, frequency=Frequency.MONTH) == 0


def test_empty_requests_validate_configuration_eagerly():
    for kwargs in (
        {"frequency": "month"},
        {"frequency": Frequency.MONTH, "month_roll": "clamp"},
    ):
        with pytest.raises(TypeError):
            make_periods(date(2026, 1, 1), count=0, **kwargs)
        with pytest.raises(TypeError):
            periods_between(date(2026, 1, 1), date(2026, 1, 1), **kwargs)
    with pytest.raises(TypeError, match="Boolean"):
        periods_between(
            date(2026, 1, 1),
            date(2026, 1, 1),
            frequency=Frequency.MONTH,
            include_partial=1,
        )
    with pytest.raises(ValueError):
        make_periods(date(2026, 1, 1), frequency=Frequency.MONTH, count=True)
    with pytest.raises(TypeError):
        offset(datetime(2026, 1, 1), frequency=Frequency.MONTH)
    with pytest.raises(ValueError, match="partial"):
        periods_between(date(2026, 1, 1), date(2026, 2, 2), frequency=Frequency.MONTH)
    periods = periods_between(
        date(2026, 1, 1),
        date(2026, 2, 2),
        frequency=Frequency.MONTH,
        include_partial=True,
    )
    assert [(p.first, p.end) for p in periods] == [
        (date(2026, 1, 1), date(2026, 2, 1)),
        (date(2026, 2, 1), date(2026, 2, 2)),
    ]


def test_derived_period_dates_do_not_become_stored_fields():
    p = make_period(date(2024, 2, 29), date(2024, 3, 1))
    assert p.first == p.last == date(2024, 2, 29)
    assert p.end == date(2024, 3, 1)
    assert set(p.to_data()) == {"start_inclusive", "end_exclusive"}
    with pytest.raises(KeyError):
        p.has_field("end")
    assert Period.from_data(p.to_data()) == p
    assert (
        Span(start_inclusive=p.first, end_exclusive=p.end, name="leap").last == p.last
    )
    flow = Flow.from_periods([p], [None], units="m", dates=[date(2024, 3, 5)])
    assert flow.movements[0].resolve(timing=PeriodTiming.FIRST) == date(2024, 3, 5)
    with pytest.raises(TypeError):
        flow.movements[0].resolve(timing="first")
    with pytest.raises(TypeError):
        p.replace(end=date(2024, 3, 2))


@pytest.mark.parametrize(
    "frequency,before,after",
    [
        (Frequency.DAY, date(2025, 12, 31), date(2026, 1, 2)),
        (Frequency.WEEK, date(2025, 12, 25), date(2026, 1, 8)),
        (Frequency.BIWEEK, date(2025, 12, 18), date(2026, 1, 15)),
        (Frequency.MONTH, date(2025, 12, 1), date(2026, 2, 1)),
        (Frequency.QUARTER, date(2025, 10, 1), date(2026, 4, 1)),
        (Frequency.HALFYEAR, date(2025, 7, 1), date(2026, 7, 1)),
        (Frequency.YEAR, date(2025, 1, 1), date(2027, 1, 1)),
        (Frequency.BIENNIUM, date(2024, 1, 1), date(2028, 1, 1)),
        (Frequency.QUINQUENNIUM, date(2021, 1, 1), date(2031, 1, 1)),
        (Frequency.DECADE, date(2016, 1, 1), date(2036, 1, 1)),
    ],
)
def test_all_frequency_offsets_and_counts_have_independent_expected_dates(
    frequency, before, after
):
    anchor = date(2026, 1, 1)
    assert offset(anchor, frequency=frequency, count=-1) == before
    assert offset(anchor, frequency=frequency, count=0) == anchor
    assert offset(anchor, frequency=frequency, count=1) == after
    assert measure(before, after, frequency=frequency) == 2
    assert measure(after, before, frequency=frequency) == -2


def test_date_range_boundaries_and_anchor_preserving_extension():
    assert offset(date.min, frequency=Frequency.DAY, count=0) == date.min
    assert offset(date.max, frequency=Frequency.MONTH, count=0) == date.max
    assert make_periods(date.max, frequency=Frequency.MONTH, count=0) == ()
    for day, count in ((date.min, -1), (date.max, 1)):
        with pytest.raises((OverflowError, ValueError)):
            offset(day, frequency=Frequency.DAY, count=count)
    remainder = periods_between(
        date(9999, 12, 30), date.max, frequency=Frequency.MONTH, include_partial=True
    )
    assert [(p.first, p.end) for p in remainder] == [(date(9999, 12, 30), date.max)]
    # Extension retains the supplied original anchor; a clamped endpoint cannot
    # determine whether the intended continuation was March 30 or March 31.
    anchor = date(2026, 1, 30)
    initial = make_periods(anchor, frequency=Frequency.MONTH, count=1)
    extended = make_periods(anchor, frequency=Frequency.MONTH, count=3)
    assert extended[:1] == initial
    assert [p.end for p in extended] == [
        date(2026, 2, 28),
        date(2026, 3, 30),
        date(2026, 4, 30),
    ]
    quarter = align(date(2026, 6, 30), frequency=Frequency.QUARTER, year_start_month=7)
    assert (quarter.first, quarter.last, quarter.end) == (
        date(2026, 4, 1),
        date(2026, 6, 30),
        date(2026, 7, 1),
    )
