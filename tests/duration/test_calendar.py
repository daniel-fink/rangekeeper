"""Independent calendar grids, anchor rules and current Period boundaries."""

from datetime import date, datetime

import pytest

from rangekeeper.duration import (
    Frequency,
    MonthGrid,
    MonthRoll,
    Period,
    Periods,
    PeriodTiming,
    Span,
    containing_period,
    count_steps,
    offset,
)
from rangekeeper.flow import Flow


def test_month_rules_keep_the_original_anchor():
    assert offset(date(2026, 4, 30), frequency=Frequency.MONTH) == date(2026, 5, 31)
    assert offset(
        date(2026, 4, 30), frequency=Frequency.MONTH, month_roll=MonthRoll.CLAMP
    ) == date(2026, 5, 30)
    for day, march in ((30, 30), (31, 31)):
        periods = Periods(start=date(2026, 1, day), frequency=Frequency.MONTH, count=2)
        assert [p.end for p in periods] == [date(2026, 2, 28), date(2026, 3, march)]
        assert periods[0].first == date(2026, 1, day)
    assert offset(date(2026, 1, 15), frequency=Frequency.MONTH, count=0) == date(
        2026, 1, 15
    )
    assert offset(date(2026, 4, 30), frequency=Frequency.WEEK) == date(2026, 5, 7)


def test_a_period_resolves_its_last_day_for_a_month_end_anchor():
    anchor = containing_period(
        on=date(2026, 1, 15), grid=MonthGrid(frequency=Frequency.MONTH)
    ).resolve(timing=PeriodTiming.LAST)
    assert anchor == date(2026, 1, 31)
    assert Periods(start=anchor, frequency=Frequency.MONTH, count=1)[0].end == date(
        2026, 2, 28
    )


def test_each_frequency_steps_by_days_or_by_months():
    for frequency in Frequency:
        days, months = frequency.step
        assert (days > 0) != (months > 0), frequency
    with pytest.raises(TypeError, match="Frequency"):
        count_steps(date(2026, 1, 1), date(2027, 1, 1), frequency="year")
    with pytest.raises(TypeError, match="MonthRoll"):
        count_steps(
            date(2026, 1, 1),
            date(2027, 1, 1),
            frequency=Frequency.YEAR,
            month_roll="clamp",
        )


def test_complete_step_measurement_is_sign_symmetric():
    a, b = date(2026, 1, 30), date(2026, 3, 29)
    assert count_steps(a, b, frequency=Frequency.MONTH) == 1
    assert count_steps(b, a, frequency=Frequency.MONTH) == -1
    assert count_steps(a, date(2026, 3, 30), frequency=Frequency.MONTH) == 2
    assert count_steps(a, a, frequency=Frequency.MONTH) == 0
    assert (
        count_steps(date(2026, 1, 1), date(2026, 1, 7), frequency=Frequency.WEEK) == 0
    )
    # Clamping a signed offset is deliberately not always inverted by measurement.
    later = date(2026, 3, 30)
    earlier = offset(later, frequency=Frequency.MONTH, count=-1)
    assert earlier == date(2026, 2, 28)
    assert count_steps(later, earlier, frequency=Frequency.MONTH) == 0


def test_empty_requests_validate_configuration_eagerly():
    month = Span(start=date(2026, 1, 1), end=date(2026, 2, 1))
    for kwargs in (
        {"frequency": "month"},
        {"frequency": Frequency.MONTH, "month_roll": "clamp"},
    ):
        with pytest.raises(TypeError):
            Periods(start=date(2026, 1, 1), count=0, **kwargs)
        with pytest.raises(TypeError):
            month.periods(**kwargs)
    with pytest.raises(TypeError, match="Boolean"):
        month.periods(frequency=Frequency.MONTH, include_partial=1)
    with pytest.raises(ValueError):
        Periods(start=date(2026, 1, 1), frequency=Frequency.MONTH, count=True)
    with pytest.raises(TypeError):
        offset(datetime(2026, 1, 1), frequency=Frequency.MONTH)
    with pytest.raises(ValueError, match="partial"):
        Span(start=date(2026, 1, 1), end=date(2026, 2, 2)).periods(
            frequency=Frequency.MONTH
        )
    periods = Span(start=date(2026, 1, 1), end=date(2026, 2, 2)).periods(
        frequency=Frequency.MONTH, include_partial=True
    )
    assert [(p.first, p.end) for p in periods] == [
        (date(2026, 1, 1), date(2026, 2, 1)),
        (date(2026, 2, 1), date(2026, 2, 2)),
    ]


def test_derived_period_dates_do_not_become_stored_fields():
    p = Period(start=date(2024, 2, 29), end=date(2024, 3, 1))
    assert p.first == p.last == date(2024, 2, 29)
    assert p.end == date(2024, 3, 1)
    assert set(p.to_data()) == {"start", "end"}
    for derived in ("first", "last"):
        with pytest.raises(KeyError):
            p.has_field(derived)
    assert Period.from_data(p.to_data()) == p
    assert Span(start=p.first, end=p.end, name="leap").last == p.last
    flow = Flow.from_periods([p], [None], units="m", dates=[date(2024, 3, 5)])
    assert flow.movements[0].resolve(timing=PeriodTiming.FIRST) == date(2024, 3, 5)
    with pytest.raises(TypeError):
        flow.movements[0].resolve(timing="first")
    with pytest.raises(TypeError):
        p.replace(last=date(2024, 3, 2))
    assert p.replace(end=date(2024, 3, 2)).last == date(2024, 3, 1)


@pytest.mark.parametrize(
    "frequency,before,after",
    [
        (Frequency.DAY, date(2025, 12, 31), date(2026, 1, 2)),
        (Frequency.WEEK, date(2025, 12, 25), date(2026, 1, 8)),
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
    assert count_steps(before, after, frequency=frequency) == 2
    assert count_steps(after, before, frequency=frequency) == -2


def test_date_range_boundaries_and_anchor_preserving_extension():
    assert offset(date.min, frequency=Frequency.DAY, count=0) == date.min
    assert offset(date.max, frequency=Frequency.MONTH, count=0) == date.max
    assert len(Periods(start=date.max, frequency=Frequency.MONTH, count=0)) == 0
    for day, count in ((date.min, -1), (date.max, 1)):
        with pytest.raises((OverflowError, ValueError)):
            offset(day, frequency=Frequency.DAY, count=count)
    remainder = Span(start=date(9999, 12, 30), end=date.max).periods(
        frequency=Frequency.MONTH, include_partial=True
    )
    assert [(p.first, p.end) for p in remainder] == [(date(9999, 12, 30), date.max)]
    # Extension retains the supplied original anchor; a clamped endpoint cannot
    # determine whether the intended continuation was March 30 or March 31.
    anchor = date(2026, 1, 30)
    initial = Periods(start=anchor, frequency=Frequency.MONTH, count=1)
    extended = Periods(start=anchor, frequency=Frequency.MONTH, count=3)
    assert extended[:1] == initial
    assert [p.end for p in extended] == [
        date(2026, 2, 28),
        date(2026, 3, 30),
        date(2026, 4, 30),
    ]


def test_year_fraction_matches_pyxirr_day_counts():
    pyxirr = pytest.importorskip("pyxirr")
    from rangekeeper.duration import DayCount, year_fraction
    from rangekeeper.finance.financial import resolve_day_count

    starts = [
        date(2019, 12, 31),
        date(2020, 2, 29),
        date(2021, 1, 31),
        date(2023, 7, 15),
    ]
    ends = [date(2020, 3, 1), date(2020, 12, 31), date(2024, 2, 29), date(2031, 5, 31)]
    for start in starts:
        for end in ends:
            for convention in DayCount:
                expected = pyxirr.year_fraction(
                    start, end, resolve_day_count(convention)
                )
                assert year_fraction(
                    start, end, convention=convention
                ) == pytest.approx(expected, rel=1e-12, abs=1e-15)
