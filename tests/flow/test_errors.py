"""Flow and Stream failures raise Rangekeeper errors with codes (#407).

A wrong Python type raises ``TypeError``. Every other failure is a
``RangekeeperError`` with an ``rk.errors.Code``; the value errors still
subclass ``ValueError``.
"""

from collections.abc import Callable
from datetime import date

import pytest

from rangekeeper.duration import AlignmentError, Frequency, Period, Periods
from rangekeeper.errors import (
    Code,
    ContractError,
    IdentityConflictError,
    MissingReferenceError,
    NumericalError,
    RangekeeperError,
    UnitError,
)
from rangekeeper.flow import AlignmentJoin, Flow, ResampleMethod, Stream

YEARS = Periods(start=date(2026, 1, 1), frequency=Frequency.YEAR, count=2)
DAYS = [date(2026, 1, 1), date(2026, 1, 2)]


def dated() -> Flow:
    return Flow.from_events(dates=DAYS, magnitudes=[1, 2], units="AUD")


def yearly() -> Flow:
    return Flow.from_periods(periods=YEARS, magnitudes=[1, 2], units="AUD")


FAILURES: list[tuple[str, Callable[[], object], type[RangekeeperError], Code]] = [
    (
        "unresolved number",
        lambda: (
            Flow.from_events(dates=DAYS[:1], magnitudes=[None], units="AUD")
            .movements[0]
            .number
        ),
        NumericalError,
        Code.NUMERICAL_FAILURE,
    ),
    (
        "unresolved total",
        lambda: Flow.from_events(
            dates=DAYS[:1], magnitudes=[None], units="AUD"
        ).total(),
        NumericalError,
        Code.NUMERICAL_FAILURE,
    ),
    (
        "unresolved aggregate",
        lambda: Stream(
            flows={
                "a": Flow.from_events(dates=DAYS[:1], magnitudes=[None], units="AUD")
            }
        ).sum(),
        NumericalError,
        Code.NUMERICAL_FAILURE,
    ),
    (
        "incompatible units",
        lambda: yearly().convert(units="m"),
        UnitError,
        Code.UNITS,
    ),
    (
        "mixed coordinates",
        lambda: dated() + yearly(),
        AlignmentError,
        Code.ALIGNMENT_MIXED,
    ),
    (
        "different coordinates",
        lambda: Stream(
            flows={"a": yearly(), "b": yearly().trim(span=YEARS[0])},
            join=AlignmentJoin.EXACT,
        ).align(),
        AlignmentError,
        Code.ALIGNMENT_DIFFER,
    ),
    (
        "different coordinates in a product",
        lambda: yearly() * yearly().trim(span=YEARS[0]),
        AlignmentError,
        Code.ALIGNMENT_DIFFER,
    ),
    (
        "gap",
        lambda: Flow.from_periods(
            periods=[YEARS[0], Period(start=date(2028, 1, 1), end=date(2029, 1, 1))],
            magnitudes=[1, 2],
            units="AUD",
        ).shift(by=1),
        AlignmentError,
        Code.ALIGNMENT_GAP,
    ),
    (
        "trim crosses",
        lambda: yearly().trim(
            span=Period(start=date(2026, 6, 1), end=date(2028, 1, 1))
        ),
        AlignmentError,
        Code.ALIGNMENT_CROSSES,
    ),
    (
        "resample crosses",
        lambda: yearly().resample(
            periods=[Period(start=date(2026, 1, 1), end=date(2026, 6, 1))],
            method=ResampleMethod.SUM,
        ),
        AlignmentError,
        Code.ALIGNMENT_CROSSES,
    ),
    (
        "frequency does not fit",
        lambda: Flow.from_periods(
            periods=YEARS[:1], magnitudes=[1], units="AUD"
        ).resample(frequency=Frequency.BIENNIUM, method=ResampleMethod.SUM),
        AlignmentError,
        Code.ALIGNMENT_PARTIAL,
    ),
    (
        "split leaves a gap",
        lambda: yearly().split(periods=YEARS[:1]),
        AlignmentError,
        Code.ALIGNMENT_GAP,
    ),
    (
        "split of dated amounts",
        lambda: dated().split(periods=YEARS),
        ContractError,
        Code.CONTRACT,
    ),
    (
        "unequal lengths",
        lambda: Flow.from_periods(periods=YEARS, magnitudes=[1], units="AUD"),
        ContractError,
        Code.CONTRACT,
    ),
    (
        "missing line",
        lambda: Stream(flows={"rent": yearly()}).select("rnet"),
        MissingReferenceError,
        Code.REFERENCE_MISSING,
    ),
    (
        "duplicate selection",
        lambda: Stream(flows={"rent": yearly()}).select("rent", "rent"),
        ContractError,
        Code.UNIQUE,
    ),
    (
        "conflicting label",
        lambda: Stream(flows={"a": yearly()}).merge(Stream(flows={"a": 2 * yearly()})),
        IdentityConflictError,
        Code.REFERENCE_IDENTITY,
    ),
    (
        "partial method mapping",
        lambda: Stream(flows={"a": yearly(), "b": yearly()}).resample(
            periods=YEARS, method={"a": ResampleMethod.SUM}
        ),
        ContractError,
        Code.CONTRACT,
    ),
]


@pytest.mark.parametrize(
    ("operation", "error", "code"),
    [failure[1:] for failure in FAILURES],
    ids=[failure[0] for failure in FAILURES],
)
def test_each_failure_has_a_rangekeeper_error_and_a_code(
    operation: Callable[[], object], error: type[RangekeeperError], code: Code
) -> None:
    with pytest.raises(error) as raised:
        operation()
    assert raised.value.code is code
    assert isinstance(raised.value, LookupError | ValueError)


def test_a_wrong_python_type_is_a_type_error() -> None:
    with pytest.raises(TypeError):
        yearly().scale("2")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Stream(flows={"a": yearly()}).dated(timing="end")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        yearly().total(missing="skip")  # type: ignore[arg-type]


def test_a_missing_line_names_the_nearest_lines() -> None:
    with pytest.raises(MissingReferenceError) as raised:
        Stream(flows={"rent": yearly(), "opex": yearly()}).select("rnet")
    assert raised.value.requested == "rnet"
    assert raised.value.candidates == ("rent",)
    assert raised.value.kind == "Flow" and raised.value.by == "name"
