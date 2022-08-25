import math
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pint
import pytest
import scipy.stats as ss
from pytest import approx

import rangekeeper as rk

# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.

matplotlib.use('TkAgg')
plt.style.use('seaborn')  # pretty matplotlib plots
plt.rcParams['figure.figsize'] = (12, 8)

units = rk.measure.Index.registry
currency = rk.measure.register_currency(
    country_code='USD',
    registry=units)
scope = dict(globals(), **locals())


class TestDistribution:
    num_periods = 100
    parameters = np.linspace(0, 1, num=num_periods)

    # print(len(parameters))

    def test_uniform_distribution_has_density_of_1(self):
        uniform_dist = rk.distribution.Uniform(generator=None)
        uniform_densities = uniform_dist.interval_density(parameters=TestDistribution.parameters)
        # plt.plot(TestDistribution.parameters, uniform_densities)
        assert sum(uniform_densities) == 1.0

    def test_exponential_distribution_total_and_initial_match(self):
        exp_dist = rk.projection.Extrapolation.Compounding(rate=0.02)
        exp_factors = exp_dist.factors(sequence=pd.RangeIndex(
            start=0,
            stop=12,
            step=1
            ))
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


class TestPeriod:
    def test_period_index_validity(self):
        date = pd.Timestamp(2020, 2, 28)
        period = rk.periodicity.include_date(
            date=date,
            duration=rk.periodicity.Type.month)
        assert period.day == 29  # end date of Period
        assert period.month == 2

        sequence = rk.periodicity.period_index(
            include_start=date,
            bound=pd.Timestamp(2020, 12, 31),
            period_type=rk.periodicity.Type.quarter)
        assert sequence.size == 4

        end_date = rk.periodicity.date_offset(
            date=date,
            period_type=rk.periodicity.Type.month,
            num_periods=4)
        assert end_date == pd.Timestamp(2020, 6, 28)


class TestUnits:
    def test_series_units(self):
        date1 = pd.Timestamp(2000, 1, 2)
        date2 = pd.Timestamp(2000, 2, 29)
        date3 = pd.Timestamp(2000, 12, 31)

        dates = [date1, date2, date3]
        values = [1 * units.meter, 2.3 * units.second, 456 * units.meter]

        series = pd.Series(
            data=values,
            index=dates,
            name="foo")
        print(series)


class TestFlow:
    date1 = pd.Timestamp(2000, 1, 2)
    date2 = pd.Timestamp(2000, 2, 29)
    date3 = pd.Timestamp(2000, 12, 31)

    dates = [date1, date2, date3]
    values = [1, 2.3, 456]

    series = pd.Series(
        data=values,
        index=dates,
        name="foo",
        dtype=float)

    flow_from_series = rk.flux.Flow(
        movements=series,
        units=currency.units)

    dict = {date1: values[0], date2: values[1], date3: values[2]}
    flow_from_dict = rk.flux.Flow.from_dict(
        movements=dict,
        name="foo",
        units=currency.units)

    def test_flow_validity(self):
        # TestFlow.flow_from_series.display()
        # TestFlow.flow_from_dict.display()
        date = pd.Timestamp(2000, 2, 29)
        assert TestFlow.flow_from_series.movements[date] == 2.3
        assert TestFlow.flow_from_series.movements.size == 3
        assert TestFlow.flow_from_series.movements.loc[date] == 2.3
        assert TestFlow.flow_from_series.movements.equals(TestFlow.flow_from_dict.movements)
        assert isinstance(TestFlow.flow_from_series.movements.index, pd.DatetimeIndex)

        TestFlow.flow_from_series.display()

    periods = rk.periodicity.period_index(
        include_start=pd.Timestamp(2020, 1, 31),
        period_type=rk.periodicity.Type.month,
        bound=pd.Timestamp(2022, 1, 1))

    print(periods.size)
    flow = rk.flux.Flow.from_projection(
        name="bar",
        value=100.0,
        proj=rk.projection.Distribution(
            dist=rk.distribution.Uniform(),
            sequence=periods),
        units=currency.units)

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

    invert_flow = flow.invert()

    def test_flow_inversion(self):
        # TestFlow.invert_flow.display()
        assert TestFlow.invert_flow.movements.size == 25
        assert TestFlow.invert_flow.movements.array.sum() == -100.0
        assert TestFlow.invert_flow.movements.index.array[2] == pd.Timestamp(2020, 3, 31)
        assert TestFlow.invert_flow.movements.array[2] == pytest.approx(-4)
        assert TestFlow.invert_flow.movements.name == "bar"
        assert TestFlow.invert_flow.units == currency.units

    resample_flow = invert_flow.resample(period_type=rk.periodicity.Type.year)

    def test_resampling(self):
        # TestFlow.resample_flow.display()
        assert TestFlow.resample_flow.movements.size == 3
        assert TestFlow.resample_flow.movements[0] == -48
        assert TestFlow.resample_flow.movements[1] == -48
        assert TestFlow.resample_flow.movements[2] == pytest.approx(-4)

    to_periods = flow.to_periods(period_type=rk.periodicity.Type.year)

    def test_conversion_to_period_index(self):
        print(TestFlow.to_periods)
        # assert TestFlow.to_periods

    def test_distribution_as_input(self):
        periods = rk.periodicity.period_index(
            include_start=pd.Timestamp(2020, 1, 31),
            period_type=rk.periodicity.Type.month,
            bound=pd.Timestamp(2022, 1, 1))

        dist = rk.distribution.PERT(
            peak=5,
            weighting=4,
            minimum=2,
            maximum=8)
        assert isinstance(dist, rk.distribution.Distribution)

        sums = []
        for i in range(1000):
            flow = rk.flux.Flow.from_projection(
                name='foo',
                value=dist,
                proj=rk.projection.Distribution(
                    dist=rk.distribution.Uniform(),
                    sequence=periods),
                units=currency.units)
            sums.append(flow.collapse().movements[0])

        # estimate distribution parameters, in this case (a, b, loc, scale)
        params = ss.beta.fit(sums)

        # evaluate PDF
        x = np.linspace(2, 8, 100)
        pdf = ss.beta.pdf(x, *params)

        # plt.hist(sums, bins=20)
        # plot
        fig, ax = plt.subplots(1, 1)
        ax.hist(sums, bins=20)
        ax.plot(x, pdf, '--r')
        plt.show(block=True)


class TestStream:
    flow1 = rk.flux.Flow.from_projection(
        name="yearly_flow",
        value=100.0,
        proj=rk.projection.Distribution(
            dist=rk.distribution.Uniform(),
            sequence=rk.periodicity.period_index(
                include_start=pd.Timestamp(2020, 1, 31),
                bound=pd.Timestamp(2022, 1, 1),
                period_type=rk.periodicity.Type.year), ),
        units=currency.units)

    flow2 = rk.flux.Flow.from_projection(
        name="weekly_flow",
        value=-50.0,
        proj=rk.projection.Distribution(
            dist=rk.distribution.Uniform(),
            sequence=rk.periodicity.period_index(
                include_start=pd.Timestamp(2020, 3, 1),
                bound=pd.Timestamp(2021, 2, 28),
                period_type=rk.periodicity.Type.week)),
        units=currency.units)

    stream = rk.flux.Stream(
        name="stream",
        flows=[flow1, flow2],
        period_type=rk.periodicity.Type.month)

    stream.display()

    def test_stream_validity(self):
        assert TestStream.stream.name == "stream"
        assert len(TestStream.stream.flows) == 2
        assert TestStream.stream.start_date == pd.Timestamp(2020, 3, 1)
        assert TestStream.stream.end_date == pd.Timestamp(2022, 12, 31)

        TestStream.stream.display()

        assert TestStream.stream.sum().movements.index.size == 24 + 10  # Two full years plus March-Dec inclusive
        assert TestStream.stream.frame['weekly_flow'].sum() == -50
        assert TestStream.stream.frame.index.freq == 'M'

        product = TestStream.stream.product(
            name="product",
            scope=dict(globals(), **locals()))
        product.display()

        datetime = pd.Timestamp(2020, 12, 31)
        print(TestStream.stream.frame['yearly_flow'][datetime])
        print(TestStream.stream.frame['weekly_flow'][datetime])
        assert product.movements[datetime] == approx(-125.786163522)

        cumsum_flow = rk.flux.Flow(
            name="cumsum_flow",
            movements=TestStream.flow1.movements.cumsum(),
            units=currency.units)
        cumsum_flow.display()
        assert cumsum_flow.movements.iloc[-1] == 100

    def test_stream_duplication(self):
        duplicate = TestStream.stream.duplicate()
        assert duplicate.name == "stream"
        assert len(duplicate.flows) == 2
        assert duplicate.frame.index.freq == 'M'

    def test_stream_stream(self):
        collapse = TestStream.stream.collapse()
        assert collapse.frame['yearly_flow'][0] == approx(100.0)

        datetime = pd.Timestamp(2020, 12, 31)
        sum = TestStream.stream.sum()
        assert sum.movements[datetime] == approx(29.5597484277)


class TestSpan:
    def test_correct_span(self):
        test_span = rk.span.Span(
            name='test_span',
            start_date=pd.Timestamp(2020, 3, 1),
            end_date=pd.Timestamp(2021, 2, 28))
        assert test_span.start_date < test_span.end_date
        assert test_span.duration(period_type=rk.periodicity.Type.day) == 364

    def test_correct_spans(self):
        dates = [pd.Timestamp(2020, 2, 29),
                 pd.Timestamp(2020, 3, 1),
                 pd.Timestamp(2021, 2, 28),
                 pd.Timestamp(2021, 12, 31),
                 pd.Timestamp(2024, 2, 29)]
        names = ['Span1', 'Span2', 'Span3', 'Span4']
        spans = rk.span.Span.from_date_sequence(names=names, dates=dates)

        assert len(spans) == 4
        assert spans[0].name == 'Span1'
        assert spans[0].end_date == pd.Timestamp(2020, 2, 29)
        assert spans[0].duration(rk.periodicity.Type.day) == 0

        assert spans[1].start_date == pd.Timestamp(2020, 3, 1)
        assert spans[1].end_date == pd.Timestamp(2021, 2, 27)


class TestMeasures:
    aud = rk.measure.register_currency(
        country_code='AUD',
        registry=units)

    def test_currency(self):
        assert TestMeasures.aud.name == 'Australian Dollar'
        assert TestMeasures.aud.units == 'AUD'
        assert TestMeasures.aud.units.dimensionality == '[currency]'

    gfa = rk.measure.Measure(
        name='Gross Floor Area',
        units=units.meter ** 2)

    nsa = rk.measure.Measure(
        name='Net Sellable Area',
        units=units.sqm)

    rent = rk.measure.Measure(
        name='Rent',
        units=aud.units)

    rent_per_nsa = rk.measure.Measure(
        name='Rent per sqm of NSA',
        units=rent.units / nsa.units)

    def test_custom_derivative(self):
        assert (1 * TestMeasures.gfa.units).to('sqm') == units.Quantity('1 * sqm')
        assert TestMeasures.rent_per_nsa.units == 'AUD / squaremeter'

    def test_eval_units(self):
        area = 100 * units.sqm
        value = 5 * (units.USD / units.sqm)
        assert area * value == units.Quantity('500 USD')

        result = eval('100 * units.sqm * 5 * (units.USD / units.sqm)')
        assert result == area * value
        assert result.units == 'USD'
        area_check = area.to('km ** 2')
        print(area.to('km ** 2'))
        assert area_check.magnitude == approx(0.0001)

        quantity_check = 100 * rk.measure.Index.registry.dimensionless
        print(quantity_check)
        assert quantity_check.units == units.dimensionless

        print((value / (5 * units.hour)).units)


class TestSpace:
    # parent_type = graph.Type(
    #     name='ParentType')
    # child_type = graph.Type(
    #     name='ChildType',
    #     parent=parent_type)
    # grandchild01_type = graph.Type(
    #     name='Grandchild01Type')
    # grandchild02_type = graph.Type(
    #     name='Grandchild02Type')
    # grandchild01_type.set_parent(child_type)
    # grandchild02_type.set_parent(child_type)
    # parent_type.set_children([child_type])
    #
    # def test_type_hierarchy(self):
    #     assert TestSpace.parent_type.children == [TestSpace.child_type]
    #     assert TestSpace.child_type.children == [TestSpace.grandchild01_type,
    #                                              TestSpace.grandchild02_type]
    #     assert TestSpace.grandchild01_type.__str__() == 'ParentType.ChildType.Grandchild01Type'
    #     print(TestSpace.grandchild02_type)

    def test_space_init(self):
        measurements = {
            TestMeasures.gfa: 12.3 * TestMeasures.gfa.units,
            TestMeasures.nsa: 4.56 * TestMeasures.nsa.units
            }
        parent_space = rk.space.Space(
            name='Parent',
            type='parent_type',
            measurements=measurements)

        assert parent_space.measurements[TestMeasures.gfa].units.dimensionality == '[length] ** 2'

        parent_space.measurements[TestMeasures.rent] = 9.81 * TestMeasures.rent_per_nsa.units * \
                                                       parent_space.measurements[TestMeasures.nsa]
        assert parent_space.measurements[TestMeasures.rent].units == 'AUD'


class TestGraph:
    def test_graph(self):
        element_root = rk.graph.Element(
            name='root',
            type='root_type')
        element_child = rk.graph.Element(
            name='child',
            type='child_type')
        element_grandchild01 = rk.graph.Element(
            name='grandchild01',
            type='grandchild_type')
        element_grandchild02 = rk.graph.Element(
            name='grandchild02',
            type='grandchild_type')

        assembly = rk.graph.Assembly(
            name='assembly',
            type='assembly_type',
            elements=[
                element_root,
                element_child,
                element_grandchild01,
                element_grandchild02],
            relationships=[
                (element_root, element_child, 'is_parent_of'),
                (element_child, element_grandchild01, 'is_parent_of'),
                (element_child, element_grandchild02, 'is_parent_of')])

        assert assembly.size() == 3
        assert assembly.has_predecessor(element_child, element_root)

        # Test Querying:
        # Check retrieval of first Element in query:
        assert assembly.elements.first(
            lambda x: x.name == 'grandchild01').type == 'grandchild_type'

        # Check count of query response:
        assert assembly.elements.count(lambda element: element.type == 'grandchild_type') == 2

        # Check retrieval of Element Relatives:
        assert [element.name for element in element_root.get_relatives(
            assembly=assembly,
            relationship_type='is_parent_of')] == ['child']

        # Check retrieval of Element Relatives in chained query:
        assert [element.name for element in assembly.elements.where(
            lambda element: element.type == 'grandchild_type').select_many(
            lambda element: element.get_relatives(
                assembly=assembly,
                relationship_type='is_parent_of',
                outgoing=False)
            ).distinct(
            lambda element: element.id)] == ['child']


class TestSegmentation:
    interval = rk.segmentation.Interval(
        right=9.6,
        left=2.4)

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
            characteristics={rk.segmentation.Characteristic.use: 'mixed'})
        (residential, podium) = gross.split(proportion=.65)

        residential.characteristics[rk.segmentation.Characteristic.use] = 'residential'
        podium.characteristics[rk.segmentation.Characteristic.use] = 'mixed'

        assert residential.bounds.right == approx(65)

        podium_subdivs = podium.subdivide(divisions=[
            ({
                 rk.segmentation.Characteristic.use: 'parking',
                 rk.segmentation.Characteristic.span: 1
                 }, 0.5),
            ({
                 rk.segmentation.Characteristic.use: 'retail',
                 rk.segmentation.Characteristic.span: 2
                 }, 0.25),
            ({
                 rk.segmentation.Characteristic.use: 'boh',
                 rk.segmentation.Characteristic.span: 2
                 }, 0.25)
            ])

        podium.display_children()

        podium.display_children(pivot=rk.segmentation.Characteristic.span)

        assert podium_subdivs[2].bounds.right == 100


class TestType:
    parent = rk.segmentation.Type(name='parent')
    child = rk.segmentation.Type(name='child')
    parent.add_subtypes([child])
    child.add_subtypes([
        rk.segmentation.Type(name='grandchild01'),
        rk.segmentation.Type(name='grandchild02')
        ])
    grandparent = rk.segmentation.Type(name='grandparent')
    grandparent.add_subtypes([parent])

    def test_heritage(self):
        assert len(TestType.grandparent.subtypes[0].subtypes[0].subtypes) == 2
        TestType.child.subtypes[0].display()
        print([ancestor.name for ancestor in TestType.child.subtypes[0].ancestors()])


class TestIO:
    def test_speckle(self):
        speckle = rk.io.Speckle.query(
            stream_id='1dd7d041b5',
            commit_id='a29679079f')
        print(speckle)

    def test_query(self):
        query = rk.io.Speckle.query2('https://speckle.xyz/streams/1dd7d041b5/objects/33cfc8f0cdfc980b783f00cc35167fc6')
        print(query)

