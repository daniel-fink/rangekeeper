"""Duration failures are Rangekeeper errors with codes (#407)."""

from datetime import date

import pytest

from rangekeeper.duration import (
    AlignmentError,
    Frequency,
    Period,
    Periods,
    Span,
    cover,
)
from rangekeeper.errors import Code, ContractError

YEARS = Periods(start=date(2026, 1, 1), frequency=Frequency.YEAR, count=3)


def test_a_trim_that_crosses_a_period_names_both():
    with pytest.raises(AlignmentError) as error:
        YEARS.trim(span=Period(start=date(2026, 7, 1), end=date(2028, 1, 1)))
    assert error.value.code is Code.ALIGNMENT_CROSSES
    assert error.value.values == {
        "span": "2026-07-01/2028-01-01",
        "period": "2026-01-01/2027-01-01",
    }
    assert isinstance(error.value, ContractError) and isinstance(
        error.value, ValueError
    )


def test_a_partial_final_period_needs_permission_and_cannot_extend():
    span = Span(start=date(2026, 1, 1), end=date(2026, 2, 15))
    with pytest.raises(AlignmentError) as error:
        span.periods(frequency=Frequency.MONTH)
    assert error.value.code is Code.ALIGNMENT_PARTIAL
    assert error.value.values == {
        "span": "2026-01-01/2026-02-15",
        "frequency": "month",
        "partial": "2026-02-01/2026-02-15",
    }
    partial = span.periods(frequency=Frequency.MONTH, include_partial=True)
    with pytest.raises(AlignmentError) as error:
        partial.extend(count=1)
    assert error.value.code is Code.ALIGNMENT_PARTIAL
    assert error.value.values["partial"] == "2026-02-01/2026-02-15"


def test_counts_slices_and_cover_raise_contract_errors():
    for call in (
        lambda: Periods(start=date(2026, 1, 1), frequency=Frequency.YEAR, count=-1),
        lambda: YEARS.extend(count=-2),
    ):
        with pytest.raises(ContractError, match="negative") as error:
            call()
        assert error.value.code is Code.CONTRACT
    for count in (1.0, "2", True):
        with pytest.raises(TypeError, match="integer"):
            YEARS.extend(count=count)
    with pytest.raises(ContractError) as error:
        YEARS[::2]
    assert error.value.values == {"step": 2}
    with pytest.raises(ContractError, match="at least one"):
        cover(periods=())
