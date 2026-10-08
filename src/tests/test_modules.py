"""Preserved numerical behaviours through canonical records and explicit operations.

Old pandas container details and implicit time-unit removal are intentional API
breaks. Dates, totals, allocation, partition meaning and detached results remain
covered here. Plotting is tested by the installed walkthroughs and adapters.
"""

from rangekeeper.model.duration import Frequency
from rangekeeper.model.flux import MissingValueHandling
from rangekeeper.calculations.series import ResamplingMethod
from rangekeeper.calculations.projection import ProjectionMethod
from rangekeeper.model.duration import MonthRoll, PeriodTiming

from rangekeeper.model import ValueKind

from rangekeeper.model.flux import Flow

from rangekeeper.model.distribution import Distribution


from datetime import date, timedelta
from uuid import uuid4
import math

import numpy as np
import pytest

from rangekeeper import Model
from rangekeeper.calculations import projection, series
from rangekeeper.calculations.interval import Interval
from rangekeeper.model.duration import make_periods, make_period, offset
from rangekeeper.model.duration.calendar import elapsed_days
from rangekeeper.model import (
    Metadata,
    System,
    Entity,
    Assembly,
    Characteristics,
    Value,
    Definitions,
    Classification,
    Taxonomy,
)
from rangekeeper.model.content import encode, decode

from rangekeeper.model.flux import Stream
from rangekeeper.model.measure import Measure, Quantity


def amounts(flow):
    return tuple(m.magnitude for m in flow.movements)


@pytest.mark.parametrize("spec", [Distribution.uniform(), Distribution.pert(mode=0.75)])
def test_distribution_mass(spec):
    masses = spec.mass([float(x) for x in np.linspace(0, 1, 100)])
    assert sum(masses) == pytest.approx(1)
    assert all(x >= 0 for x in masses)


def test_projection_compounding():
    factors = projection.project_values(
        1, count=12, method=ProjectionMethod.COMPOUND, rate=0.02
    )
    assert factors[-1] == (1.02**11)


def test_month_end_is_explicit_and_period_end_is_exclusive():
    assert offset(
        date(2020, 2, 29),
        frequency=Frequency.MONTH,
        count=3,
        month_roll=MonthRoll.PRESERVE_END,
    ) == date(2020, 5, 31)
    period = make_period(date(2020, 2, 1), date(2020, 3, 1))
    assert period.end_exclusive - timedelta(days=1) == date(2020, 2, 29)
    assert elapsed_days(period.start_inclusive, period.end_exclusive) == 29


def test_flow_construction_detachment_and_negation():
    dates = (date(2000, 1, 2), date(2000, 2, 29), date(2000, 12, 31))
    original = Flow.from_events(dates, (1, 2.3, 456), units="AUD")
    assert original.movements[1].date == dates[1]
    assert original.movements[1].magnitude == 2.3
    detached = original.to_data()
    duplicate = Flow.from_data(detached)
    detached["movements"][0]["magnitude"] = 100
    assert duplicate == original
    assert original.total().magnitude == pytest.approx(459.3)
    assert amounts(original.negate()) == pytest.approx((-1, -2.3, -456))
    assert original.movements[0].magnitude == 1


def test_allocation_and_annual_resampling_preserve_total():
    periods = make_periods(date(2020, 1, 1), frequency=Frequency.MONTH, count=25)
    flow = projection.allocate(Quantity(magnitude=100, units="AUD"), periods=periods)
    assert amounts(flow) == pytest.approx((4,) * 25)
    years = make_periods(date(2020, 1, 1), frequency=Frequency.YEAR, count=3)
    reduced = series.resample(flow.negate(), periods=years, method=ResamplingMethod.SUM)
    assert amounts(reduced.flow) == pytest.approx((-48, -48, -4))
    assert reduced.flow.total().magnitude == pytest.approx(-100)


@pytest.mark.parametrize("frequency", ["day", "month", "quarter", "year"])
def test_resampling_uses_declared_calendar_bins(frequency):
    source = Flow.from_events(
        (date(2020, 1, 31), date(2020, 2, 29), date(2020, 3, 31)),
        (1, 2, 3),
        units="meter",
    )
    count = {"day": 91, "month": 3, "quarter": 1, "year": 1}[frequency]
    periods = make_periods(
        date(2020, 1, 1), frequency=Frequency(frequency), count=count
    )
    result = series.resample(
        source,
        periods=periods,
        method=ResamplingMethod.SUM,
        missing=MissingValueHandling.ZERO,
    )
    assert result.flow.total().magnitude == 6
    assert tuple(m.period for m in result.flow.movements) == periods


def test_sampling_is_explicit_before_allocation():
    spec = Distribution.pert(lower=2, upper=8, mode=5, weighting=4, units="AUD")
    draws = spec.sample(size=20, generator=np.random.default_rng(23))
    assert all(2 <= x <= 8 for x in draws)
    periods = make_periods(date(2020, 1, 1), frequency=Frequency.MONTH, count=25)
    for amount in draws:
        flow = projection.allocate(
            Quantity(magnitude=amount, units="AUD"), periods=periods
        )
        assert flow.total().magnitude == pytest.approx(amount)


def test_stream_selection_and_mixed_frequency_totals():
    measure = Measure(id=uuid4(), code="cash", name="Cash", units="AUD")
    flows = [
        projection.allocate(
            Quantity(magnitude=total, units="AUD"),
            periods=make_periods(
                date(2020, 1, 1),
                frequency=Frequency(freq),
                count=count,
            ),
        )
        for total, freq, count in (
            (100, "year", 3),
            (-50, "week", 53),
            (-50, "biweek", 53),
        )
    ]
    values = tuple(
        Value(
            id=uuid4(),
            key=f"flow-{i}",
            kind=ValueKind.FLOW,
            measure=measure.id,
            flow=flow,
        )
        for i, flow in enumerate(flows)
    )
    owner = Entity(id=uuid4(), characteristics=Characteristics(values=values))
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        definitions=Definitions(measures=(measure,)),
        system=System(entities=(owner,)),
    )
    stream = Stream.from_values(model, tuple(v.id for v in values))
    assert stream.merge(stream).values == stream.values
    assert stream.select(value_ids=(values[1].id,)).values == (values[1],)
    years = make_periods(date(2020, 1, 1), frequency=Frequency.YEAR, count=3)
    # Weekly coverage can cross a calendar-year boundary. Select payment timing
    # explicitly; a bounded coverage interval must not be assigned by accident.
    with pytest.raises(ValueError, match="crosses"):
        series.resample(
            flows[1],
            periods=years,
            method=ResamplingMethod.SUM,
            missing=MissingValueHandling.ZERO,
        )
    payments = tuple(
        Flow.from_events(
            [m.resolve(timing=PeriodTiming.LAST) for m in value.flow.movements],
            amounts(value.flow),
            units=value.flow.units,
        )
        for value in stream.values
    )
    annual = tuple(
        series.resample(
            flow,
            periods=years,
            method=ResamplingMethod.SUM,
            missing=MissingValueHandling.ZERO,
        ).flow
        for flow in payments
    )
    assert series.aggregate(annual).flow.total().magnitude == pytest.approx(
        0, abs=1e-12
    )


def test_product_preserves_units_and_explicit_exposure_removes_time():
    periods = make_periods(date(2020, 1, 1), frequency=Frequency.MONTH, count=1)
    rate = Flow.from_periods(periods, (math.pi,), units="AUD/meter**2/month")
    factor = Flow.from_periods(periods, (2,), units="dimensionless")
    product = series.multiply((rate, factor))
    assert product.convert(units="AUD/meter**2/month").movements[
        0
    ].magnitude == pytest.approx(2 * math.pi)
    integrated = series.integrate(
        product, exposures=(Quantity(magnitude=1, units="month"),), units="AUD/meter**2"
    )
    assert integrated.movements[0].magnitude == pytest.approx(2 * math.pi)


def test_interval_partition_boundaries():
    interval = Interval(2.4, 9.6)
    assert (interval.left + interval.right) / 2 == 6
    assert interval.length == pytest.approx(7.2)
    left, right = interval.split(1 / 3)
    assert (right.left, right.right, right.length) == pytest.approx((4.8, 9.6, 4.8))
    pieces = interval.subdivide(4)
    assert pieces[0].right == pytest.approx(4.2)
    assert pieces[-1].right == 9.6
    assert pieces[0].subdivide((0.1, 0.2, 0.7))[0].right == pytest.approx(2.58)


def test_segment_meaning_is_model_content_not_a_second_mutable_tree():
    residential, podium = Interval(0, 100).split(0.65)
    pieces = podium.subdivide((0.5, 0.25, 0.25))
    children = tuple(
        Entity(
            id=uuid4(),
            name=name,
            characteristics=Characteristics(
                values=(
                    Value(
                        id=uuid4(),
                        key="bounds",
                        kind=ValueKind.PROPERTY,
                        content=encode((bounds.left, bounds.right)),
                    ),
                    Value(
                        id=uuid4(),
                        key="span",
                        kind=ValueKind.PROPERTY,
                        content=encode(span),
                    ),
                )
            ),
        )
        for name, bounds, span in zip(("Parking", "Retail", "BOH"), pieces, (1, 2, 2))
    )
    parent = Assembly(id=uuid4(), name="Podium", entities=tuple(c.id for c in children))
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        system=System(entities=children, assemblies=(parent,)),
    )
    assert residential.right == 65
    assert (
        decode(model.value(children[-1].characteristics.values[0].id).content)[1] == 100
    )
    assert tuple(decode(c.characteristics.values[1].content) for c in children) == (
        1,
        2,
        2,
    )
    assert model.entity(parent.id).entities == tuple(c.id for c in children)


def test_type_ancestry_uses_canonical_classification_references():
    grandparent = Classification(id=uuid4(), code="grandparent", name="Grandparent")
    parent = Classification(
        id=uuid4(), code="parent", name="Parent", parent=grandparent.id
    )
    child = Classification(id=uuid4(), code="child", name="Child", parent=parent.id)
    leaves = tuple(
        Classification(id=uuid4(), code=f"leaf-{i}", name=f"Leaf {i}", parent=child.id)
        for i in range(2)
    )
    taxonomy = Taxonomy(
        id=uuid4(),
        code="types",
        name="Types",
        classifications=(grandparent, parent, child, *leaves),
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        definitions=Definitions(taxonomies=(taxonomy,)),
    )
    records = {c.id: c for c in model.definitions.taxonomies[0].classifications}
    assert sum(c.parent == child.id for c in records.values()) == 2
    current, names = leaves[0], []
    while current.parent is not None:
        current = records[current.parent]
        names.append(current.name)
    assert names == ["Child", "Parent", "Grandparent"]
