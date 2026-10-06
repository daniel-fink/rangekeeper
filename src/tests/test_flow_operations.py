"""Flows carry quantities; model-selected operations supply their interpretation."""
from rangekeeper.model.flow import Flow

from rangekeeper.calculations.account import Account


from datetime import date
import json

import pytest

from rangekeeper.calculations import series

from rangekeeper.errors import ValidationError
from rangekeeper.model.flow import Movement
from rangekeeper.model.measure import Quantity
from rangekeeper.duration import make_period, make_periods


@pytest.mark.parametrize("field", ["basis", "kind"])
def test_flow_wire_contract_rejects_semantic_classification(field):
    flow = Flow.from_events([date(2026, 1, 1)], [100], units="AUD")
    payload = flow.to_data()
    assert set(payload) == {"units", "movements"}
    assert Flow.from_json(json.dumps(payload)) == flow
    with pytest.raises(ValidationError):
        Flow.from_data({**payload, field: "movement"})


@pytest.mark.parametrize("include_movements", [False, True])
def test_old_samples_field_is_rejected_instead_of_losing_entries(include_movements):
    movement = Movement(key="payment", date=date(2026, 1, 1), magnitude=100)
    payload = {"units": "AUD", "samples": [movement.to_data()]}
    if include_movements:
        payload["movements"] = []
    with pytest.raises(ValidationError):
        Flow.from_data(payload)


@pytest.mark.parametrize(
    "reduction,expected",
    [("sum", 30), ("first", 10), ("last", 20), ("min", 10), ("max", 20), ("mean", 15)],
)
def test_model_can_select_different_reductions_for_the_same_flow(reduction, expected):
    flow = Flow.from_events(
        [date(2026, 1, 1), date(2026, 1, 31)], [10, 20], units="AUD"
    )
    before = flow.to_data()
    result = series.resample(
        flow,
        periods=[make_period(date(2026, 1, 1), date(2026, 2, 1))],
        reduction=reduction,
        weighting="observations" if reduction == "mean" else None,
    ).flow
    assert result.movements[0].magnitude == expected
    assert result.units == "AUD" and flow.to_data() == before


def test_means_require_a_choice_and_do_not_infer_weighting_from_units():
    periods = make_periods(date(2026, 1, 1), frequency="month", count=2)
    flow = Flow.from_periods(periods, [10, 20], units="dimensionless")
    target = [make_period(periods[0].start, periods[-1].end)]
    with pytest.raises(ValueError, match="weighting"):
        series.resample(flow, periods=target, reduction="mean")
    observed = series.resample(
        flow, periods=target, reduction="mean", weighting="observations"
    ).flow
    elapsed = series.resample(
        flow, periods=target, reduction="mean", weighting="elapsed"
    ).flow
    assert observed.movements[0].magnitude == 15
    assert elapsed.movements[0].magnitude == pytest.approx((31 * 10 + 28 * 20) / 59)


def test_products_preserve_time_dimensions_and_scaled_dimensionless_units():
    periods = make_periods(date(2026, 1, 1), frequency="month", count=1)
    rates = Flow.from_periods(periods, [2], units="AUD/day")
    factors = Flow.from_periods(periods, [50], units="percent")
    squared = series.multiply((rates, rates, factors)).convert(units="AUD**2/day**2")
    assert squared.movements[0].magnitude == 2
    dimensionless = series.multiply((factors, factors))
    assert dimensionless.units == "dimensionless"
    assert dimensionless.movements[0].magnitude == 0.25


def test_exposure_is_an_explicit_operation_without_a_rate_classification():
    length = Flow.from_events([date(2026, 1, 1)], [2], units="m")
    area = series.integrate(
        length, exposures=[Quantity(magnitude=3, units="m")], units="m**2"
    )
    assert area.movements[0].magnitude == 6
    assert length.movements[0].magnitude == 2
    with pytest.raises(ValueError, match="exposures or day_count"):
        series.integrate(length)


def test_account_argument_defines_rate_role_and_checks_units():
    periods = make_periods(date(2026, 1, 1), frequency="month", count=2)
    transactions = Flow.from_periods(periods, [0, 0], units="AUD")
    rates = Flow.from_periods(periods, [10, 20], units="percent")
    result = Account.calculate(
        transactions,
        starting=Quantity(magnitude=100, units="AUD"),
        rate=rates,
        method="compound",
    )
    assert [s.magnitude for s in result.closing.movements] == pytest.approx([110, 132])
    assert [s.magnitude for s in result.interest.movements] == pytest.approx([10, 22])
    with pytest.raises(ValueError, match="incompatible"):
        Account.calculate(
            transactions,
            starting=Quantity(magnitude=100, units="AUD"),
            rate=transactions,
        )


@pytest.mark.parametrize("reduction", ["sum", "last", "mean"])
def test_explicit_zero_fill_does_not_resolve_present_unknowns(reduction):
    periods = make_periods(date(2026, 1, 1), frequency="month", count=3)
    flow = Flow.from_periods(periods[:2], [10, None], units="AUD")
    result = series.resample(
        flow,
        periods=periods,
        reduction=reduction,
        weighting="observations" if reduction == "mean" else None,
        missing="zero",
    )
    assert [s.magnitude for s in result.flow.movements] == [10, None, 0]
    assert result.coverage == (1, 0, 0)
