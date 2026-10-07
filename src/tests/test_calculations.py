"""Independent temporal/calculation oracles and explicit migration corrections."""

from rangekeeper.model.content import ContentKind

from rangekeeper.duration import Frequency, PeriodTiming, DayCount
from rangekeeper.model.flow import MissingValueHandling
from rangekeeper.calculations.series import (
    AlignmentJoin,
    AggregationReducer,
    ResamplingReduction,
    MeanWeighting,
)
from rangekeeper.calculations.projection import ProjectionMethod, PaddingMode
from rangekeeper.account import Balance, CurrentInterest, InterestTreatment
from rangekeeper._schema.enums import ValueKind, DistributionFamily

from rangekeeper.calculations.account import Account
from rangekeeper.model.distribution import Distribution
from rangekeeper.model.flow import Flow

from datetime import date, datetime, time, timedelta
from types import MappingProxyType
from uuid import uuid4
from zoneinfo import ZoneInfo
import math
import numpy as np
import pytest
from rangekeeper import Model
from rangekeeper.model.content import encode, decode
from rangekeeper.model.flow import Stream
from rangekeeper._schema.records import (
    Metadata,
    Entity,
    Value,
    Characteristics,
    Definitions,
    Measure,
    System,
    PropertyContent,
)
from rangekeeper.model.measure import Quantity
from rangekeeper.model import distribution as distributions
from rangekeeper.duration import make_periods, make_period, offset, year_fraction
from rangekeeper.calculations import series, projection, financial, account
from rangekeeper.calculations.interval import Interval
from rangekeeper.io import json as codec
from rangekeeper.io.memory import MemoryStore


def annual(values, *, units="AUD"):
    return Flow.from_periods(
        make_periods(date(2020, 1, 1), frequency=Frequency.YEAR, count=len(values)),
        values,
        units=units,
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        False,
        True,
        0,
        1,
        1.0,
        -0.0,
        "",
        uuid4(),
        date(2020, 2, 29),
        datetime(2020, 1, 1),
        datetime(2020, 11, 1, 1, 30, fold=1, tzinfo=ZoneInfo("America/New_York")),
        time(12, 30),
        timedelta(days=-2, microseconds=3),
        [],
        (),
        set(),
        frozenset(),
        {"a": [False, 1, 1.0], "b": (None, timedelta(days=2))},
        MappingProxyType({"a": frozenset({1, 2})}),
    ],
)
def test_typed_content_roundtrip(value):
    content = encode(value)
    restored = decode(
        PropertyContent.from_json(__import__("json").dumps(content.to_data()))
    )
    assert type(restored) is type(value) and restored == value
    if type(value) is float:
        assert math.copysign(1, restored) == math.copysign(1, value)
    if isinstance(value, datetime):
        assert restored.fold == value.fold
        assert getattr(restored.tzinfo, "key", None) == getattr(
            value.tzinfo, "key", None
        )


def test_property_detachment_and_rejections():
    original = {"a": [1]}
    content = encode(original)
    original["a"].append(2)
    exported = decode(content)
    exported["a"].append(3)
    assert decode(content) == {"a": [1]}
    with pytest.raises(AttributeError):
        content.kind = "list"
    cycle = []
    cycle.append(cycle)
    for item in (cycle, float("nan"), object()):
        with pytest.raises((ValueError, TypeError)):
            encode(item)
    for data in (
        {"kind": "integer", "text": "01"},
        {"kind": "null", "text": "oops"},
        {"kind": "list"},
        {"kind": "float", "text": "nan"},
    ):
        with pytest.raises((ValueError, TypeError)):
            decode(PropertyContent.from_data(data))


def test_model_flow_content_store_and_stream():
    flow = annual([0, None, 3])
    measure = Measure(id=uuid4(), code="rent", name="Rent", units=flow.units)
    a = Value(
        id=uuid4(), key="rent", kind=ValueKind.FLOW, measure=measure.id, flow=flow
    )
    b = Value(
        id=uuid4(),
        key="other",
        kind=ValueKind.FLOW,
        measure=measure.id,
        flow=flow.clone(),
    )
    prop = Value(
        id=uuid4(),
        key="source",
        kind=ValueKind.PROPERTY,
        content=encode({"zero": 0, "false": False}),
    )
    entity = Entity(id=uuid4(), characteristics=Characteristics(values=(a, b, prop)))
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        definitions=Definitions(measures=(measure,)),
        system=System(entities=(entity,)),
    )
    stream = Stream.from_values(model, (a.id, b.id))
    assert stream.select(value_ids=(b.id,)).values == (b,)
    assert len(stream.merge(stream).values) == 2
    with pytest.raises(ValueError):
        Stream.from_values(model, (a.id, a.id))
    with pytest.raises(ValueError):
        Stream.from_values(model, (prop.id,))
    assert model.owner_of(a.id) == entity.id
    store = MemoryStore()
    store.put(model)
    restored = codec.loads(codec.dumps(model), kind=Model)
    assert restored.to_data() == model.to_data() == store.load_model(model.id).to_data()
    from rangekeeper.io import yaml

    restored_yaml = yaml.loads(yaml.dumps(model), kind=Model)
    assert restored_yaml.to_data() == model.to_data()
    assert (
        type(restored_yaml.value(a.id).flow.movements[0].period.start_inclusive) is date
    )
    data = restored.to_data()
    data["system"]["entities"][0]["characteristics"]["values"][0]["flow"]["movements"][
        0
    ]["magnitude"] = 10
    assert model.value(a.id).flow.movements[0].magnitude == 0
    with pytest.raises(AttributeError):
        model.value(a.id).flow.movements[0].magnitude = 10
    # Model validation must follow the renamed collection when resolving evidence.
    invalid = model.to_data()
    invalid["system"]["entities"][0]["characteristics"]["values"][0]["flow"][
        "movements"
    ][0]["claims"] = [str(uuid4())]
    with pytest.raises(ValueError, match="unknown movement Claim"):
        Model.from_data(invalid)


@pytest.mark.parametrize(
    "frequency,count,end",
    [
        ("day", 2, date(2020, 1, 3)),
        ("week", 2, date(2020, 1, 15)),
        ("biweek", 2, date(2020, 1, 29)),
        ("month", 2, date(2020, 3, 1)),
        ("quarter", 2, date(2020, 7, 1)),
        ("halfyear", 2, date(2021, 1, 1)),
        ("year", 2, date(2022, 1, 1)),
        ("biennium", 2, date(2024, 1, 1)),
        ("quinquennium", 2, date(2030, 1, 1)),
        ("decade", 2, date(2040, 1, 1)),
    ],
)
def test_calendar_frequencies(frequency, count, end):
    periods = make_periods(
        date(2020, 1, 1), frequency=Frequency(frequency), count=count
    )
    assert periods[-1].end == end and periods[0].end == periods[1].start_inclusive


def test_month_anchor_and_leap_year():
    periods = make_periods(date(2020, 1, 31), frequency=Frequency.MONTH, count=2)
    assert periods[0].end == date(2020, 2, 29)
    assert periods[1].end == date(2020, 3, 31)
    assert offset(date(2020, 3, 31), frequency=Frequency.MONTH, count=-1) == date(
        2020, 2, 29
    )
    assert (
        year_fraction(
            date(2020, 1, 1), date(2021, 1, 1), convention=DayCount.ACTUAL_ACTUAL
        )
        == 1
    )


def test_duplicate_events_order_and_periods():
    today = date(2020, 1, 1)
    with pytest.raises(ValueError, match="repeated event|duplicate"):
        Flow.from_events([today, today], [1, 2], units="m")
    flow = Flow.from_events(
        [today, today], [1, 2], units="m", keys=["delivery-1", "delivery-2"]
    )
    assert flow.total().magnitude == 3
    with pytest.raises(ValueError):
        Flow.from_events([date(2021, 1, 1), today], [1, 2], units="m")
    with pytest.raises(ValueError):
        Flow.from_periods([make_period(today, date(2020, 2, 1))] * 2, [1, 2], units="m")


def test_units_and_factor_product():
    rent = annual([100, 200], units="AUD/month")
    factor = annual([120, 50], units="percent")
    result = series.multiply((rent, factor)).convert(units="AUD/month")
    assert [s.magnitude for s in result.movements] == [120, 100]
    amount = series.integrate(
        rent, exposures=(Quantity(magnitude=2, units="month"),) * 2, units="AUD"
    )
    assert [s.magnitude for s in amount.movements] == [200, 400]
    # Summation preserves units; the model decides whether it is meaningful.
    assert rent.total().magnitude == 300
    assert rent.total().units == "AUD/month"
    with pytest.raises(ValueError):
        series.aggregate((annual([1]), annual([1], units="USD")))
    length = annual([1], units="m")
    assert (
        series.aggregate((length, annual([100], units="cm")))
        .flow.movements[0]
        .magnitude
        == 2
    )
    assert series.multiply((length, length)).units == "meter ** 2"


def test_explicit_calendar_integration():
    periods = make_periods(date(2020, 1, 1), frequency=Frequency.MONTH, count=2)
    rates = Flow.from_periods(periods, [3660, 3660], units="AUD/year")
    assert [
        s.magnitude
        for s in series.integrate(
            rates, day_count=DayCount.ACTUAL_ACTUAL, units="AUD"
        ).movements
    ] == pytest.approx([310, 290])


def test_missing_alignment_and_coverage():
    a = annual([1, None, 0])
    b = annual([2, 3, 4])
    with pytest.raises(ValueError):
        series.aggregate((a, b))
    result = series.aggregate((a, b), missing=MissingValueHandling.PROPAGATE)
    assert [s.magnitude for s in result.flow.movements] == [
        3,
        None,
        4,
    ] and result.coverage == (1, 0.5, 1)
    assert (
        series.aggregate((a, b), missing=MissingValueHandling.SKIP)
        .flow.movements[1]
        .magnitude
        == 3
    )
    assert (
        series.aggregate(
            (annual([None]), annual([None])), missing=MissingValueHandling.SKIP
        )
        .flow.movements[0]
        .magnitude
        is None
    )
    with pytest.raises(ValueError):
        series.align((a, annual([1])))
    aligned = series.align(
        (a, annual([1])), join=AlignmentJoin.UNION, missing=MissingValueHandling.ZERO
    )
    assert (
        aligned.flows[0].movements[1].magnitude is None
        and aligned.flows[1].movements[1].magnitude == 0
    )


def test_resample_complete_calendar_and_explicit_reduction():
    flow = Flow.from_events(
        [date(2020, 1, 1), date(2020, 1, 31), date(2020, 3, 1)],
        [10, 20, 40],
        units="kWh",
    )
    periods = make_periods(date(2020, 1, 1), frequency=Frequency.MONTH, count=3)
    with pytest.raises(ValueError):
        series.resample(flow, periods=periods, reduction=ResamplingReduction.SUM)
    result = series.resample(
        flow,
        periods=periods,
        reduction=ResamplingReduction.SUM,
        missing=MissingValueHandling.ZERO,
    )
    assert [s.magnitude for s in result.flow.movements] == [
        30,
        0,
        40,
    ] and result.coverage == (1, 0, 1)
    assert result.flow.total().magnitude == 70
    stocks = Flow.from_events(
        [date(2020, 1, 1), date(2020, 1, 31)], [10, 20], units="kWh"
    )
    assert (
        series.resample(stocks, periods=periods[:1], reduction=ResamplingReduction.LAST)
        .flow.movements[0]
        .magnitude
        == 20
    )
    assert (
        series.resample(stocks, periods=periods[:1], reduction=ResamplingReduction.SUM)
        .flow.movements[0]
        .magnitude
        == 30
    )


@pytest.mark.parametrize("kind", ["uniform", "triangular", "pert"])
def test_distribution_sampling_and_mass(kind):
    dist = Distribution.symmetric(kind=DistributionFamily(kind), mean=2, residual=1)
    assert sum(dist.mass([1, 1.5, 2, 2.5, 3])) == pytest.approx(1)
    assert dist.sample(size=5, generator=np.random.default_rng(7)) == dist.sample(
        size=5, generator=np.random.default_rng(7)
    )
    assert Distribution.symmetric(
        kind=DistributionFamily(kind), mean=2, residual=0
    ).sample(size=3, generator=np.random.default_rng(7)) == (2, 2, 2)
    with pytest.raises(ValueError):
        dist.mass([1, 3, 2])


def test_projection_and_partition_invariants():
    assert projection.project_values(
        100, count=3, method=ProjectionMethod.LINEAR, rate=2
    ) == (
        100,
        102,
        104,
    )
    assert projection.project_values(
        100, count=3, method=ProjectionMethod.COMPOUND, rate=0.1
    ) == pytest.approx((100, 110, 121))
    assert projection.pad(
        [2, 3], before=1, after=2, left=PaddingMode.UNITIZE, right=PaddingMode.EXTEND
    ) == (1, 2, 3, 3, 3)
    periods = make_periods(date(2020, 1, 1), frequency=Frequency.MONTH, count=7)
    flow = projection.allocate(
        Quantity(magnitude=100, units="kg"),
        periods=periods,
        distribution=Distribution.pert(),
    )
    assert flow.total().magnitude == pytest.approx(100)
    pieces = Interval(3, 13).subdivide((0.2, 0.3, 0.5))
    assert sum(p.length for p in pieces) == 10 and pieces[0].right == pieces[1].left
    with pytest.raises(ValueError):
        Interval(0, 1).subdivide(0)


def test_financial_independent_examples():
    flow = Flow.from_events(
        [date(2021, 1, 1), date(2022, 1, 1)], [-100, 110], units="AUD"
    )
    assert financial.calculate_xnpv(
        flow, rate=0.1, valuation_date=date(2021, 1, 1)
    ).magnitude == pytest.approx(0, abs=1e-12)
    result = financial.calculate_irr(flow)
    assert result.rate == pytest.approx(0.1) and abs(result.residual.magnitude) < 1e-9
    assert [
        s.magnitude
        for s in financial.calculate_pv(annual([110, 121]), rate=0.1).movements
    ] == pytest.approx([100, 100])
    with pytest.raises(ValueError):
        financial.calculate_irr(flow, guess=-1)


@pytest.mark.parametrize(
    "method,expected",
    [("simple", 100), ("compound", 121), ("capitalized", 100 / 0.9**2)],
)
def test_account_interest_modes(method, expected):
    result = Account.calculate(
        annual([0, 0]),
        starting=Quantity(magnitude=100, units="AUD"),
        rate=0.1,
        treatment=(
            InterestTreatment.SEPARATE
            if method == "simple"
            else InterestTreatment.FINANCED
        ),
        current_interest=(
            CurrentInterest.INCLUDED
            if method == "capitalized"
            else CurrentInterest.EXCLUDED
        ),
    )
    assert result.closing.movements[-1].magnitude == pytest.approx(expected)
    if method != "simple":
        assert result.interest.total().magnitude == pytest.approx(expected - 100)


def test_account_overdraft_and_timing():
    result = Account.calculate(
        annual([-150, 100, -200]), starting=Quantity(magnitude=100, units="AUD")
    )
    assert [s.magnitude for s in result.closing.movements] == [0, 50, 0]
    assert [s.magnitude for s in result.overdraft_balance.movements] == [-50, 0, -150]
    assert [s.magnitude for s in result.overdraft.movements] == [-50, 50, -150]
    for timing, interest in [("advance", 11), ("arrears", 10)]:
        result = Account.calculate(
            annual([10]),
            starting=Quantity(magnitude=100, units="AUD"),
            rate=0.1,
            balance=Balance.CLOSING if timing == "advance" else Balance.OPENING,
        )
        assert result.interest.movements[0].magnitude == pytest.approx(interest)


def test_adapter_exports_are_detached():
    from rangekeeper.adapters import polars as po

    flow = annual([0, None, 2])
    frame = po.to_frame(flow)
    assert po.from_frame(frame, units=flow.units) == flow
    cells = frame.to_dicts()
    cells[0]["period"]["start_inclusive"] = "2000-01-01"
    assert flow.movements[0].period.start_inclusive == date(2020, 1, 1)


def test_dynamics_fixed_inputs():
    from rangekeeper.calculations.dynamics.cyclicality import calculate_cycle
    from rangekeeper.calculations.dynamics.volatility import (
        calculate_autoregression,
        accumulate_volatility,
    )
    from rangekeeper.calculations.dynamics.shock import calculate_shock

    assert calculate_cycle(count=4, period=4, phase=0, amplitude=2) == pytest.approx(
        [0, 2, 0, -2]
    )
    assert calculate_autoregression([1, 0, 0], parameter=0.5) == (1, 0.5, 0.25)
    assert accumulate_volatility(
        [100, 110, 121], [0, 0.1, 0], growth_rate=0.1, mean_reversion=0.5
    ) == pytest.approx([100, 120, 127])
    assert calculate_shock(
        [0.8, 0.1, 0.05, 0.2], likelihood=0.2, dissipation=0.5, impact=-0.4
    ) == (0, -0.4, -0.2, -0.1)


def test_weighted_rates_and_partial_period_helpers():
    from rangekeeper.duration import periods_between, cover

    periods = make_periods(date(2020, 1, 1), frequency=Frequency.MONTH, count=2)
    rates = Flow.from_periods(periods, (10, 20), units="AUD/year")
    target = (make_period(date(2020, 1, 1), date(2020, 3, 1)),)
    with pytest.raises(ValueError, match="weighting"):
        series.resample(rates, periods=target, reduction=ResamplingReduction.MEAN)
    result = series.resample(
        rates,
        periods=target,
        reduction=ResamplingReduction.MEAN,
        weighting=MeanWeighting.ELAPSED,
    )
    assert result.flow.movements[0].magnitude == pytest.approx((31 * 10 + 29 * 20) / 60)
    assert (
        series.resample(
            rates,
            periods=target,
            reduction=ResamplingReduction.MEAN,
            weighting=MeanWeighting.OBSERVATIONS,
        )
        .flow.movements[0]
        .magnitude
        == 15
    )
    assert cover(periods).end == periods[-1].end
    with pytest.raises(ValueError, match="partial"):
        periods_between(date(2020, 1, 1), date(2020, 2, 2), frequency=Frequency.MONTH)
    assert (
        len(
            periods_between(
                date(2020, 1, 1),
                date(2020, 2, 2),
                frequency=Frequency.MONTH,
                include_partial=True,
            )
        )
        == 2
    )
    assert [s.magnitude for s in annual([0, 2, None, 3, 0]).trim_empty().movements] == [
        2,
        None,
        3,
    ]
    assert (
        series.aggregate(
            (annual([1, 4]), annual([3, 2])), reducer=AggregationReducer.MIN
        )
        .flow.movements[1]
        .magnitude
        == 2
    )


def test_distinct_property_and_flow_roles_reject_malformed_content():
    from tests.test_execution import data
    from rangekeeper.errors import ValidationError

    base = data("model")
    value = base["system"]["entities"][0]["characteristics"]["values"][0]
    value["content"] = encode("invalid extra content").to_data()
    with pytest.raises(ValidationError):
        Model.from_data(base)


def test_polars_preserves_explicit_null_and_omission():
    from rangekeeper.model.flow import Flow
    from rangekeeper.adapters.polars import to_frame, from_frame

    flow = Flow.from_data(
        {
            "units": "meter",
            "movements": [
                {
                    "id": str(uuid4()),
                    "key": "a",
                    "date": None,
                    "period": {
                        "start_inclusive": "2020-01-01",
                        "end_exclusive": "2020-01-02",
                    },
                    "claims": None,
                },
                {
                    "id": str(uuid4()),
                    "key": "b",
                    "period": {
                        "start_inclusive": "2020-01-02",
                        "end_exclusive": "2020-01-03",
                    },
                    "magnitude": None,
                },
            ],
        }
    )
    assert from_frame(to_frame(flow), units=flow.units).to_data() == flow.to_data()


def test_invalid_timezone_is_a_domain_validation_error():
    with pytest.raises(ValueError, match="property content"):
        decode(
            PropertyContent(
                kind=ContentKind.DATETIME,
                text="2020-01-01T00:00:00+00:00",
                zone="Invalid/Nowhere",
            )
        )
