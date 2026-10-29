"""Flow and Stream construction, lookup, arithmetic, shift and resample (G02–G05)."""

from datetime import date
from decimal import Decimal

import pytest

import rangekeeper as rk
from rangekeeper.duration import Frequency, PeriodTiming, Span
from rangekeeper.errors import (
    AmbiguousReferenceError,
    MissingReferenceError,
    NumericalError,
    UnitError,
)
from rangekeeper.flow import Flow, MissingValueHandling, ResampleMethod, Stream
from rangekeeper.quantity import Quantity

HOLDING = Span(start=date(2001, 1, 1), length="10 years", name="Holding")
YEARS = HOLDING.extend(by="1 year").periods(frequency=Frequency.YEAR)


def growing(units="USD"):
    return Flow(amounts={p: 100 * 1.02**i for i, p in enumerate(YEARS)}, units=units)


def test_flow_from_a_mapping_of_periods():
    flow = Flow(amounts={YEARS[1]: 102, YEARS[0]: 100}, units="USD")
    assert [m.period for m in flow.movements] == [YEARS[0], YEARS[1]]
    assert [m.magnitude for m in flow.movements] == [Decimal(100), Decimal(102)]
    assert flow == Flow.from_periods(YEARS[:2], [100, 102], units="USD")


def test_flow_from_a_mapping_of_dates_and_quantities():
    flow = Flow(amounts={date(2001, 1, 1): -Quantity(text="1000 USD")})
    assert flow.units == "USD"
    assert flow.movements[0].date == date(2001, 1, 1)
    assert flow == Flow.from_events([date(2001, 1, 1)], [-1000], units="USD")
    converted = Flow(amounts={date(2001, 1, 1): "1 km", date(2002, 1, 1): 5}, units="m")
    assert [m.magnitude for m in converted.movements] == [1000.0, 5]


@pytest.mark.parametrize(
    ("arguments", "error"),
    [
        ({"amounts": {YEARS[0]: 1}}, TypeError),
        ({"amounts": {YEARS[0]: 1, date(2001, 1, 1): 1}, "units": "m"}, TypeError),
        ({"amounts": {YEARS[0]: object()}, "units": "m"}, TypeError),
        ({"amounts": {YEARS[0]: 1}, "movements": (), "units": "m"}, TypeError),
        ({"amounts": [1], "units": "m"}, TypeError),
    ],
)
def test_flow_construction_errors(arguments, error):
    with pytest.raises(error):
        Flow(**arguments)


def test_at_returns_the_amount_on_a_date():
    flow = growing()
    assert flow.at(on=date(2010, 6, 30)) == Quantity(text="119.509256862231 USD")
    with pytest.raises(MissingReferenceError):
        flow.at(on=date(1999, 1, 1))
    events = Flow.from_events(
        [date(2001, 1, 1)] * 2, [1, 2], units="USD", keys=["a", "b"]
    )
    with pytest.raises(AmbiguousReferenceError):
        events.at(on=date(2001, 1, 1))
    with pytest.raises(NumericalError):
        Flow.from_periods(YEARS[:1], [None], units="USD").at(on=date(2001, 1, 1))


def test_arithmetic_with_numbers_and_quantities():
    flow = growing()
    assert (-0.05 * flow).at(on=date(2001, 1, 1)) == Quantity(text="-5 USD")
    assert (flow * 2).at(on=date(2002, 1, 1)) == Quantity(text="204 USD")
    divided = flow / Quantity(text="5 %")
    assert divided.at(on=date(2001, 1, 1)) == Quantity(text="2000 USD")
    assert divided.at(on=date(2005, 1, 1)) == flow.at(on=date(2005, 1, 1)) / Quantity(
        text="5 %"
    )
    assert (flow / 4).at(on=date(2001, 1, 1)) == Quantity(text="25 USD")
    rent = Flow.from_periods(YEARS[:1], [750], units="AUD per sqm pa")
    assert (rent * Quantity(text="100 sqm")).units == "AUD * pa"
    assert (Quantity(text="100 sqm") * rent).units == "AUD * pa"
    assert (-flow).at(on=date(2001, 1, 1)) == Quantity(text="-100 USD")
    with pytest.raises(TypeError):
        _ = 1 / flow  # type: ignore[operator]


def test_addition_matches_coordinates_and_keeps_the_others():
    flow = growing()
    assert flow - 0.5 * flow == 0.5 * flow
    first = flow.trim(span=YEARS[0])
    total = flow + first
    assert total.at(on=date(2001, 1, 1)) == Quantity(text="200 USD")
    assert total.at(on=date(2002, 1, 1)) == Quantity(text="102 USD")
    assert (first - flow).at(on=date(2002, 1, 1)) == Quantity(text="-102 USD")
    with pytest.raises(UnitError):
        _ = flow + growing(units="AUD")
    dated = Flow.from_events([date(2001, 1, 1)], [1], units="USD")
    with pytest.raises(ValueError, match="Stream.sum"):
        _ = flow + dated
    unresolved = Flow.from_periods(YEARS[:1], [None], units="USD")
    assert (flow + unresolved).movements[0].magnitude is None


def test_flow_times_flow_needs_the_same_coordinates():
    flow = growing()
    assert (flow * flow).units == "USD ** 2"
    assert (flow / flow).at(on=date(2003, 1, 1)) == Quantity(text="1 dimensionless")
    with pytest.raises(ValueError, match="coordinates"):
        _ = flow * flow.trim(span=YEARS[0])


def test_shift_moves_amounts_by_whole_periods():
    flow = growing()
    earlier = flow.shift(by=-1)
    assert [m.period for m in earlier.movements] == list(YEARS)
    assert earlier.at(on=date(2001, 1, 1)) == flow.at(on=date(2002, 1, 1))
    assert earlier.movements[-1].magnitude is None
    later = flow.shift(by=2)
    assert later.movements[0].magnitude is None
    assert later.at(on=date(2003, 1, 1)) == flow.at(on=date(2001, 1, 1))
    assert flow.shift(by=0) == flow
    with pytest.raises(ValueError, match="Periods"):
        Flow.from_events([date(2001, 1, 1)], [1], units="USD").shift(by=1)
    gap = Flow.from_periods([YEARS[0], YEARS[2]], [1, 2], units="USD")
    with pytest.raises(ValueError, match="gap-free"):
        gap.shift(by=1)
    with pytest.raises(TypeError):
        flow.shift(by=1.0)  # type: ignore[arg-type]


def test_trim_takes_a_period_or_a_span():
    flow = growing()
    assert len(flow.trim(span=HOLDING).movements) == 10
    assert flow.trim(span=YEARS[-1]).total() == flow.at(on=date(2011, 1, 1))
    with pytest.raises(TypeError):
        flow.trim(HOLDING)  # type: ignore[misc]


def test_split_and_sum_round_trip():
    flow = growing()
    quarters = flow.split(frequency=Frequency.QUARTER)
    assert len(quarters.movements) == 44
    assert quarters.at(on=date(2001, 2, 1)) == Quantity(text="25 USD")
    assert (
        quarters.resample(frequency=Frequency.YEAR, method=ResampleMethod.SUM) == flow
    )
    assert quarters.trim(span=YEARS[3]).total() == flow.at(on=date(2004, 1, 1))
    with pytest.raises(ValueError, match="partition"):
        flow.split(
            periods=Span(start=date(2001, 1, 1), length="1 year").periods(
                frequency=Frequency.QUARTER
            )[1:],
        )
    with pytest.raises(ValueError, match="do not end"):
        flow.trim(span=YEARS[0]).resample(
            frequency=Frequency.BIENNIUM, method=ResampleMethod.SUM
        )
    with pytest.raises(TypeError):
        flow.resample(method=ResampleMethod.SUM)
    with pytest.raises(TypeError):
        flow.split()
    with pytest.raises(ValueError, match="period movements"):
        Flow.from_events([date(2001, 1, 1)], [1], units="USD").split(periods=YEARS[:1])


def test_stream_construction_lookup_and_with_flows():
    flow = growing()
    stream = Stream(flows={"PGI": flow, "Vacancy": -0.05 * flow})
    assert stream["PGI"] is flow
    with pytest.raises(MissingReferenceError, match="PGI"):
        stream["PGl"]
    wider = stream.with_flows(flows={"Vacancy": -0.1 * flow, "OPEX": -0.35 * flow})
    assert wider.names == ("PGI", "Vacancy", "OPEX")
    assert wider["Vacancy"] == -0.1 * flow
    assert stream.names == ("PGI", "Vacancy")
    assert wider.select("OPEX", "PGI").names == ("OPEX", "PGI")
    with pytest.raises(TypeError):
        Stream({"PGI": flow})  # type: ignore[misc]


def test_stream_sum_adds_lines_with_different_coordinates():
    flow = growing()
    stream = Stream(flows={"NACF": flow, "Terminal value": flow.trim(span=YEARS[3])})
    total = stream.trim(span=HOLDING).sum()
    assert len(total.movements) == 10
    assert total.at(on=date(2004, 1, 1)) == 2 * flow.at(on=date(2004, 1, 1))
    assert total.at(on=date(2005, 1, 1)) == flow.at(on=date(2005, 1, 1))
    unresolved = Stream(
        flows={"a": flow, "b": Flow.from_periods(YEARS[:1], [None], units="USD")}
    )
    with pytest.raises(ValueError, match="unresolved"):
        unresolved.sum()
    assert unresolved.with_policy(missing=MissingValueHandling.SKIP).sum() == flow


def test_stream_sum_dates_period_amounts_when_lines_mix():
    flow = growing().trim(span=HOLDING)
    purchase = Flow(amounts={HOLDING.start: Quantity(text="-1000 USD")})
    investment = Stream(flows={"Purchase": purchase, "Cash flows": flow}).sum()
    assert [m.date for m in investment.movements][:3] == [
        date(2001, 1, 1),
        date(2002, 1, 1),
        date(2003, 1, 1),
    ]
    assert investment.at(on=date(2011, 1, 1)) == flow.at(on=date(2010, 1, 1))
    first = (
        Stream(flows={"Purchase": purchase, "Cash flows": flow})
        .dated(timing=PeriodTiming.FIRST)
        .sum()
    )
    assert first.at(on=date(2001, 1, 1)) == Quantity(text="-900 USD")
    dated = Stream(flows={"a": flow}).dated()
    assert dated["a"].movements[0].date == date(2002, 1, 1)
    assert dated["a"].movements[0].period is None
    with pytest.raises(TypeError, match="PeriodTiming"):
        Stream(flows={"a": flow}).dated(timing="end")  # type: ignore[arg-type]


def test_stream_resample_with_a_frequency():
    flow = growing()
    stream = Stream(flows={"a": flow, "b": 2 * flow})
    quarters = stream.split(frequency=Frequency.QUARTER)
    assert quarters["b"].at(on=date(2001, 1, 1)) == Quantity(text="50 USD")
    years = quarters.resample(frequency=Frequency.YEAR, method=ResampleMethod.SUM)
    assert years["a"] == flow
    with pytest.raises(ValueError, match="cover every label"):
        stream.resample(frequency=Frequency.YEAR, method={"a": ResampleMethod.SUM})


def test_root_names():
    assert rk.flow.ResampleMethod is ResampleMethod
    assert not hasattr(rk.flow, "ResamplingMethod")
    assert not hasattr(rk.flow, "MeanWeighting")
    assert "split" not in {member.value for member in ResampleMethod}
