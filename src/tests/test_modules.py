import datetime
import locale
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
import scipy.stats as ss
from pytest import approx

import rangekeeper as rk

# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.

# matplotlib.use('TkAgg')
plt.style.use("seaborn-v0_8")  # pretty matplotlib plots
plt.rcParams["figure.figsize"] = (12, 8)

locale = locale.setlocale(locale.LC_ALL, "en_AU")
units = rk.measure.Index.registry
currency = rk.measure.register_currency(registry=units)
scope = dict(globals(), **locals())


class TestDistribution:
    num_periods = 100
    parameters = np.linspace(0, 1, num=num_periods)

    # print(len(parameters))

    def test_uniform_distribution_has_density_of_1(self):
        uniform_dist = rk.distribution.Uniform(generator=None)
        uniform_densities = uniform_dist.interval_density(
            parameters=TestDistribution.parameters
        )
        # plt.plot(TestDistribution.parameters, uniform_densities)
        assert sum(uniform_densities) == 1.0

    def test_exponential_distribution_total_and_initial_match(self):
        exp_form = rk.extrapolation.Compounding(rate=0.02)
        exp_factors = exp_form.terms(sequence=pd.RangeIndex(start=0, stop=12, step=1))
        # exp_densities = exp_dist.density(parameters=TestDistribution.parameters)
        # exp_cumulative = exp_dist.cumulative_density(parameters=TestDistribution.parameters)

        # plt.plot(parameters, exp_factors)
        # plt.plot(TestDistribution.parameters, exp_densities)
        # plt.plot(TestDistribution.parameters, exp_cumulative)
        assert exp_factors[11] == math.pow((1 + 0.02), 11)

    def test_PERT_distribution_sums_to_1(self):
        pert_dist = rk.distribution.PERT(peak=0.75, weighting=4)
        pert_values = pert_dist.interval_density(parameters=TestDistribution.parameters)
        # plt.plot(TestDistribution.parameters, pert_values)
        # print("PERT CDF: " + str(pert_values))
        assert sum(pert_values) == 1.0

        # print(pert_value)


class TestDuration:
    def test_offset(self):
        date = datetime.date(2020, 2, 29)
        offset_eom = rk.duration.offset(
            date=date, duration=rk.duration.Type.MONTH, amount=3
        )
        assert offset_eom == datetime.date(2020, 5, 31)


class TestPeriod:
    def test_period_index_validity(self):
        date = datetime.date(2020, 2, 28)
        period = rk.duration.Period.include_date(
            date=date,
            duration=rk.duration.Type.MONTH,
        )
        assert period.day == 29  # end date of Period
        # assert period.month == 2
        #
        # sequence = rk.duration.Sequence.from_bounds(
        #     include_start=date,
        #     bound=datetime.date(2020, 12, 31),
        #     frequency=rk.duration.Type.QUARTER,
        # )
        # assert sequence.size == 4
        #
        # end_date = rk.duration.offset(
        #     date=date, duration=rk.duration.Type.MONTH, amount=4
        # )
        # assert end_date == datetime.date(2020, 6, 28)


class TestUnits:
    def test_series_units(self):
        date1 = datetime.date(2000, 1, 2)
        date2 = datetime.date(2000, 2, 29)
        date3 = datetime.date(2000, 12, 31)

        dates = [date1, date2, date3]
        values = [1 * units.meter, 2.3 * units.second, 456 * units.meter]

        series = pd.Series(data=values, index=dates, name="foo")
        print(series)

    def test_remove_dim(self):
        quantity = math.pi * currency.units / units.squaremeter / units.month
        reduced_quantity = rk.measure.remove_dimension(
            quantity=quantity, dimension="[time]", registry=units
        )
        assert reduced_quantity == math.pi * currency.units / units.squaremeter

    def test_multiply_units(self):
        q1 = math.pi * currency.units / units.squaremeter / units.month
        q2 = math.e * units.meter / units.year
        q3 = math.tau * units.dimensionless

        quantities = [q1, q2, q3]
        product = rk.measure.multiply_units(
            units=[quantity.units for quantity in quantities], registry=units
        )
        assert product == "AUD * meter / month / squaremeter / year"


class TestFlow:
    date1 = datetime.date(2000, 1, 2)
    date2 = datetime.date(2000, 2, 29)
    date3 = datetime.date(2000, 12, 31)

    dates = [date1, date2, date3]
    values = [1, 2.3, 456]

    series = pd.Series(
        data=values,
        index=[pd.Timestamp(date) for date in dates],
        name="foo",
        dtype=float,
    )

    flow_from_series = rk.flux.Flow(movements=series, units=currency.units)

    dict = {
        date1: values[0],
        date2: values[1],
        date3: values[2],
    }
    flow_from_dict = rk.flux.Flow.from_dict(
        movements=dict,
        name="foo",
        units=currency.units,
    )

    def test_flow_validity(self):
        # TestFlow.flow_from_series.display()
        # TestFlow.flow_from_dict.display()
        datestamp = pd.Timestamp(2000, 2, 29)
        assert TestFlow.flow_from_series.movements[datestamp] == 2.3
        assert TestFlow.flow_from_series.movements.size == 3
        assert TestFlow.flow_from_series.movements.loc[datestamp] == 2.3
        assert TestFlow.flow_from_series.movements.equals(
            TestFlow.flow_from_dict.movements
        )
        assert isinstance(TestFlow.flow_from_series.movements.index, pd.DatetimeIndex)

        TestFlow.flow_from_series.display()

    periods = rk.duration.Sequence.from_bounds(
        include_start=datetime.date(2020, 1, 31),
        frequency=rk.duration.Type.MONTH,
        bound=datetime.date(2022, 1, 1),
    )

    print(periods.size)
    flow = rk.flux.Flow.from_projection(
        name="bar",
        value=100.0,
        proj=rk.projection.Distribution(
            form=rk.distribution.Uniform(), sequence=periods
        ),
        units=currency.units,
    )

    def test_flow_duplication(self):
        duplicate = TestFlow.flow.duplicate()
        assert duplicate.movements.equals(TestFlow.flow.movements)
        assert duplicate.movements.size == TestFlow.flow.movements.size
        assert duplicate.movements.index.equals(TestFlow.flow.movements.index)

    def test_flow_summation(self):
        # TestFlow.sum_flow.display()
        assert TestFlow.flow.movements.size == 25
        assert TestFlow.flow.movements.array.sum() == 100.0
        assert TestFlow.flow.movements.index.array[1] == pd.Timestamp(2020, 2, 29)
        assert TestFlow.flow.movements.array[1] == 4
        assert TestFlow.flow.movements.name == "bar"
        assert TestFlow.flow.units == currency.units

        TestFlow.flow.display()
        collapse = TestFlow.flow.collapse()
        collapse.display()
        assert collapse.movements.size == 1
        assert collapse.movements.array[0] == 100.0

    invert_flow = flow.negate()

    def test_flow_inversion(self):
        # TestFlow.invert_flow.display()
        assert TestFlow.invert_flow.movements.size == 25
        assert TestFlow.invert_flow.movements.array.sum() == -100.0
        assert TestFlow.invert_flow.movements.index.array[2] == pd.Timestamp(
            2020, 3, 31
        )
        assert TestFlow.invert_flow.movements.array[2] == pytest.approx(-4)
        assert TestFlow.invert_flow.movements.name == "bar"
        assert TestFlow.invert_flow.units == currency.units

    resample_flow = invert_flow.resample(frequency=rk.duration.Type.YEAR)

    def test_resampling(self):
        # TestFlow.resample_flow.display()
        assert TestFlow.resample_flow.movements.size == 3
        assert TestFlow.resample_flow.movements.iloc[0] == -48
        assert TestFlow.resample_flow.movements.iloc[1] == -48
        assert TestFlow.resample_flow.movements.iloc[2] == pytest.approx(-4)

    # to_periods = flow.to_periods(index=rk.duration.Type.YEAR)

    def test_conversion_to_period_index(self):
        pass
        # print(TestFlow.to_periods)
        # assert TestFlow.to_periods

        # resampled = TestFlow.invert_flow.resample(frequency=rk.duration.Type.BIWEEK)
        # resampled.display()

        # fortnightly = TestFlow.invert_flow.to_periods(frequency=rk.duration.Type.BIWEEK)
        # print(fortnightly)

    def test_distribution_as_input(self):
        periods = rk.duration.Sequence.from_bounds(
            include_start=datetime.date(2020, 1, 31),
            frequency=rk.duration.Type.MONTH,
            bound=datetime.date(2022, 1, 1),
        )

        dist = rk.distribution.PERT(peak=5, weighting=4, minimum=2, maximum=8)
        assert isinstance(dist, rk.distribution.Form)

        sums = []
        for i in range(1000):
            flow = rk.flux.Flow.from_projection(
                name="foo",
                value=dist,
                proj=rk.projection.Distribution(
                    form=rk.distribution.Uniform(), sequence=periods
                ),
                units=currency.units,
            )
            sums.append(flow.collapse().movements.iloc[0])

        # estimate distribution parameters, in this case (a, b, loc, scale)
        params = ss.beta.fit(sums)

        # evaluate PDF
        x = np.linspace(2, 8, 100)
        pdf = ss.beta.pdf(x, *params)

        # plt.hist(sums, bins=20)
        # plot
        fig, ax = plt.subplots(1, 1)
        ax.hist(sums, bins=20)
        ax.plot(x, pdf, "--r")
        plt.show(block=True)

    def test_total(self):
        total = TestFlow.flow.total()

        print(total)


class TestStream:
    flow1 = rk.flux.Flow.from_projection(
        name="yearly_flow",
        value=100.0,
        proj=rk.projection.Distribution(
            form=rk.distribution.Uniform(),
            sequence=rk.duration.Sequence.from_bounds(
                include_start=datetime.date(2020, 1, 31),
                bound=datetime.date(2022, 1, 1),
                frequency=rk.duration.Type.YEAR,
            ),
        ),
        units=currency.units,
    )

    flow2 = rk.flux.Flow.from_projection(
        name="weekly_flow",
        value=-50.0,
        proj=rk.projection.Distribution(
            form=rk.distribution.Uniform(),
            sequence=rk.duration.Sequence.from_bounds(
                include_start=datetime.date(2020, 3, 1),
                bound=datetime.date(2021, 2, 28),
                frequency=rk.duration.Type.WEEK,
            ),
        ),
        units=currency.units,
    )

    flow3 = rk.flux.Flow.from_projection(
        name="fortnightly_flow",
        value=-50.0,
        proj=rk.projection.Distribution(
            form=rk.distribution.Uniform(),
            sequence=rk.duration.Sequence.from_bounds(
                include_start=datetime.date(2020, 1, 31),
                bound=datetime.date(2022, 1, 1),
                frequency=rk.duration.Type.BIWEEK,
            ),
        ),
        units=currency.units,
    )

    stream = rk.flux.Stream(
        name="stream",
        flows=[flow1, flow2, flow3],
        frequency=rk.duration.Type.BIWEEK,
    )

    def test_stream_validity(self):
        print(f"\nFlows:\n")
        TestStream.flow1.display()
        TestStream.flow2.display()
        TestStream.flow3.display()

        print(f"\nResampled: \n")
        TestStream.flow1.resample(
            frequency=rk.duration.Type.BIWEEK,
            origin=pd.Timestamp(2020, 2, 9),
        ).display()
        TestStream.flow2.resample(
            frequency=rk.duration.Type.BIWEEK,
            origin=pd.Timestamp(2020, 2, 9),
        ).display()
        TestStream.flow3.resample(
            frequency=rk.duration.Type.BIWEEK,
            origin=pd.Timestamp(2020, 2, 9),
        ).display()

        TestStream.stream.display()
        TestStream.stream.sum().display()

        # # TestStream.flow1.display()
        # TestStream.flow1.resample(frequency=rk.duration.Type.BIWEEK).display()
        # #
        # print(TestStream.flow1.to_periods(index=TestStream.stream.index).to_string())

        assert TestStream.stream.name == "stream"
        assert len(TestStream.stream.flows) == 3
        assert TestStream.stream.start_date == pd.Timestamp(2020, 2, 9)
        assert TestStream.stream.end_date == pd.Timestamp(2022, 12, 31)

        assert TestStream.stream.total() == approx(100 - 50 - 50)

        # assert (
        #     TestStream.stream.sum().movements.index.size == 24 + 10
        # )  # Two full years plus March-Dec inclusive
        # assert TestStream.stream.frame["weekly_flow"].sum() == -50
        # assert TestStream.stream.frame.index.freqstr == "M"
        #
        # product = TestStream.stream.product(
        #     name="product",
        #     registry=units,
        # )
        # product.display()
        #
        # datestamp = pd.Timestamp(2020, 12, 31)
        # print(TestStream.stream.frame["yearly_flow"][datestamp])
        # print(TestStream.stream.frame["weekly_flow"][datestamp])
        # assert product.movements[datestamp] == approx(-125.786163522)
        #
        # cumsum_flow = rk.flux.Flow(
        #     name="cumsum_flow",
        #     movements=TestStream.flow1.movements.cumsum(),
        #     units=currency.units,
        # )
        # cumsum_flow.display()
        # assert cumsum_flow.movements.iloc[-1] == 100

    def test_stream_aggregation(self):
        flow2_sqm = TestStream.flow2.duplicate()
        flow2_sqm.units = units.squaremeter / units.month

        stream_sqm = rk.flux.Stream(
            name="stream_sqm",
            flows=[TestStream.flow1, flow2_sqm],
            frequency=rk.duration.Type.MONTH,
        )

        stream_sqm_agg = stream_sqm.product(
            name="stream_sqm_agg",
            registry=units,
        )

        assert stream_sqm_agg.units == "AUD * squaremeter"

    def test_stream_duplication(self):
        duplicate = TestStream.stream.duplicate()
        assert duplicate.name == "stream"
        assert len(duplicate.flows) == 3
        assert duplicate.frame.index.freqstr == "2W-SUN"

    def test_stream_stream(self):
        collapse = TestStream.stream.collapse()
        collapse.display()
        assert collapse.frame["yearly_flow"].iloc[0] == approx(100.0)

        datestamp = pd.Timestamp(2022, 1, 9)
        sum = TestStream.stream.sum()
        sum.display()
        assert sum.movements[datestamp] == approx(32.3529, rel=1e-4)


class TestSpan:
    def test_correct_span(self):
        test_span = rk.duration.Span(
            name="test_span",
            start_date=datetime.date(2020, 3, 1),
            end_date=datetime.date(2021, 2, 28),
        )
        assert test_span.start_date < test_span.end_date
        assert test_span.duration(type=rk.duration.Type.DAY, inclusive=False) == 364

    def test_correct_spans(self):
        dates = [
            datetime.date(2020, 2, 29),
            datetime.date(2020, 3, 1),
            datetime.date(2021, 2, 28),
            datetime.date(2021, 12, 31),
            datetime.date(2024, 2, 29),
        ]
        names = ["Span1", "Span2", "Span3", "Span4"]
        spans = rk.duration.Span.from_date_sequence(names=names, dates=dates)

        assert len(spans) == 4
        assert spans[0].name == "Span1"
        assert spans[0].end_date == datetime.date(2020, 2, 29)
        assert spans[0].duration(type=rk.duration.Type.DAY) == 0

        assert spans[1].start_date == datetime.date(2020, 3, 1)
        assert spans[1].end_date == datetime.date(2021, 2, 27)


class TestSegmentation:
    interval = rk.segmentation.Interval(right=9.6, left=2.4)

    def test_interval(self):
        assert TestSegmentation.interval.mid == approx(6.0)
        assert TestSegmentation.interval.length == approx(7.2)

        (left_child, right_child) = TestSegmentation.interval.split(proportion=(1 / 3))
        assert right_child.right == approx(9.6)
        assert right_child.left == approx(4.8)
        assert right_child.length == approx(4.8)
        assert right_child.mid == approx(7.2)

        children = TestSegmentation.interval.subdivide(values=4)
        print(children)
        assert children[0].left == 2.4
        assert children[0].right == approx(4.2)
        assert children[3].right == approx(9.6)
        assert children[2].length == approx(1.8)

        grandchildren = children[0].subdivide(values=[0.1, 0.2, 0.7])
        assert grandchildren[0].left == 2.4
        assert grandchildren[0].right == 2.58

    def test_division(self):
        gross = rk.segmentation.Segment(
            bounds=rk.segmentation.Interval(right=100),
            characteristics={rk.segmentation.Characteristic.use: "mixed"},
        )
        (residential, podium) = gross.split(proportion=0.65)

        residential.characteristics[rk.segmentation.Characteristic.use] = "residential"
        podium.characteristics[rk.segmentation.Characteristic.use] = "mixed"

        assert residential.bounds.right == approx(65)

        podium_subdivs = podium.subdivide(
            divisions=[
                (
                    "Parking",
                    {
                        rk.segmentation.Characteristic.type: "Podium",
                        rk.segmentation.Characteristic.tenure: "Mixed",
                        rk.segmentation.Characteristic.use: "Parking",
                        rk.segmentation.Characteristic.span: 1,
                    },
                    0.5,
                ),
                (
                    "Retail",
                    {
                        rk.segmentation.Characteristic.type: "Podium",
                        rk.segmentation.Characteristic.tenure: "Mixed",
                        rk.segmentation.Characteristic.use: "Retail",
                        rk.segmentation.Characteristic.span: 2,
                    },
                    0.25,
                ),
                (
                    "boh",
                    {
                        rk.segmentation.Characteristic.type: "Podium",
                        rk.segmentation.Characteristic.tenure: "Mixed",
                        rk.segmentation.Characteristic.use: "BOH",
                        rk.segmentation.Characteristic.span: 2,
                    },
                    0.25,
                ),
            ]
        )

        podium.display_children()

        podium.display_children(pivot=rk.segmentation.Characteristic.span)

        assert podium_subdivs[2].bounds.right == 100


class TestType:
    parent = rk.segmentation.Type(name="parent")
    child = rk.segmentation.Type(name="child")
    parent.add_subtypes([child])
    child.add_subtypes(
        [
            rk.segmentation.Type(name="grandchild01"),
            rk.segmentation.Type(name="grandchild02"),
        ]
    )
    grandparent = rk.segmentation.Type(name="grandparent")
    grandparent.add_subtypes([parent])

    def test_heritage(self):
        assert len(TestType.grandparent.subtypes[0].subtypes[0].subtypes) == 2
        TestType.child.subtypes[0].display()
        print([ancestor.name for ancestor in TestType.child.subtypes[0].ancestors()])


# class TestAPI:
# def test_speckle(self):
#     speckle = rk.api.Speckle(token='52c9b20071b2854f98ad91af10c154ad5e232b88a7')
#     item = speckle.get_item(
#         stream_id='1dd7d041b5',
#         commit_id='a29679079f')
#     print(item)
#     print(item.Data)
#
#
# def test_query(self):
#     query = rk.api.Speckle.query2('https://speckle.xyz/streams/1dd7d041b5/objects/33cfc8f0cdfc980b783f00cc35167fc6')
#     print(query)
