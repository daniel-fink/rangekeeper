import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pint
from pint import definitions
import scipy.stats as ss

try:
    import distribution
    import flux
    import phase
    import measure
    import space
    from periodicity import Periodicity
except:
    import modules.rangekeeper.distribution
    import modules.rangekeeper.flux
    import modules.rangekeeper.phase
    import modules.rangekeeper.measure
    import modules.rangekeeper.space
    from modules.rangekeeper.periodicity import Periodicity


# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.

matplotlib.use('TkAgg')
plt.style.use('seaborn')  # pretty matplotlib plots
plt.rcParams['figure.figsize'] = (12, 8)

units = pint.UnitRegistry()
currency = measure.add_currency(
    country_code='USD',
    unit_registry=units)


class TestDistribution:
    num_periods = 100
    parameters = np.linspace(0, 1, num=num_periods)

    # print(len(parameters))

    def test_uniform_distribution_has_density_of_1(self):
        uniform_dist = distribution.Uniform(generator=None)
        uniform_densities = uniform_dist.interval_density(parameters=TestDistribution.parameters)
        # plt.plot(TestDistribution.parameters, uniform_densities)
        assert sum(uniform_densities) == 1.0

    def test_exponential_distribution_total_and_initial_match(self):
        exp_dist = distribution.Exponential(rate=0.02, num_periods=12)
        exp_factors = exp_dist.factor()
        # exp_densities = exp_dist.density(parameters=TestDistribution.parameters)
        # exp_cumulative = exp_dist.cumulative_density(parameters=TestDistribution.parameters)

        # plt.plot(parameters, exp_factors)
        # plt.plot(TestDistribution.parameters, exp_densities)
        # plt.plot(TestDistribution.parameters, exp_cumulative)
        # assert exp_factors[100 - 1] == math.pow((1 + 0.02), 100)

    def test_PERT_distribution_sums_to_1(self):
        pert_dist = distribution.PERT(peak=0.75, weighting=4)
        pert_values = pert_dist.interval_density(parameters=TestDistribution.parameters)
        # plt.plot(TestDistribution.parameters, pert_values)
        # print("PERT CDF: " + str(pert_values))
        assert sum(pert_values) == 1.0

        # print(pert_value)


class TestPeriod:
    def test_period_index_validity(self):
        date = pd.Timestamp(2020, 2, 28)
        period = Periodicity.include_date(date=date, duration=Periodicity.Type.month)
        assert period.day == 29  # end date of Period
        assert period.month == 2

        sequence = Periodicity.period_index(include_start=date,
                                            bound=pd.Timestamp(2020, 12, 31),
                                            periodicity=Periodicity.Type.quarter)
        assert sequence.size == 4

        end_date = Periodicity.date_offset(date, Periodicity.Type.month, 4)
        assert end_date == pd.Timestamp(2020, 6, 28)


class TestFlow:
    date1 = pd.Timestamp(2000, 1, 2)
    date2 = pd.Timestamp(2000, 2, 29)
    date3 = pd.Timestamp(2000, 12, 31)

    dates = [date1, date2, date3]
    values = [1, 2.3, 456]

    series = pd.Series(data=values, index=dates, name="foo", dtype=float)
    flow_from_series = flux.Flow(movements=series, units=currency)

    dict = {date1: values[0], date2: values[1], date3: values[2]}
    flow_from_dict = flux.Flow.from_dict(movements=dict, name="foo", units=currency)

    def test_flow_validity(self):
        # TestFlow.flow_from_series.display()
        # TestFlow.flow_from_dict.display()
        date = pd.Timestamp(2000, 2, 29)
        assert TestFlow.flow_from_series.movements[date] == 2.3
        assert TestFlow.flow_from_series.movements.size == 3
        assert TestFlow.flow_from_series.movements.loc[date] == 2.3
        assert TestFlow.flow_from_series.movements.equals(TestFlow.flow_from_dict.movements)
        assert isinstance(TestFlow.flow_from_series.movements.index, pd.DatetimeIndex)

    periods = Periodicity.period_index(include_start=pd.Timestamp(2020, 1, 31),
                                       periodicity=Periodicity.Type.month,
                                       bound=pd.Timestamp(2022, 1, 1))

    flow = flux.Flow.from_total(name="bar",
                                total=100.0,
                                index=Periodicity.to_datestamps(periods),
                                dist=distribution.Uniform(),
                                units=currency)

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
        assert TestFlow.flow.units == currency

    invert_flow = flow.invert()

    def test_flow_inversion(self):
        # TestFlow.invert_flow.display()
        assert TestFlow.invert_flow.movements.size == 25
        assert TestFlow.invert_flow.movements.array.sum() == -100.0
        assert TestFlow.invert_flow.movements.index.array[2] == pd.Timestamp(2020, 3, 31)
        assert TestFlow.invert_flow.movements.array[2] == -4
        assert TestFlow.invert_flow.movements.name == "bar"
        assert TestFlow.invert_flow.units == currency

    resample_flow = invert_flow.resample(periodicity=Periodicity.Type.year)

    def test_resampling(self):
        # TestFlow.resample_flow.display()
        assert TestFlow.resample_flow.movements.size == 3
        assert TestFlow.resample_flow.movements[0] == -48
        assert TestFlow.resample_flow.movements[1] == -48
        assert TestFlow.resample_flow.movements[2] == -4

    to_periods = flow.to_periods(periodicity=Periodicity.Type.year)

    def test_conversion_to_period_index(self):
        print(TestFlow.to_periods)
        # assert TestFlow.to_periods

    def test_distribution_as_input(self):
        periods = Periodicity.period_index(include_start=pd.Timestamp(2020, 1, 31),
                                           periodicity=Periodicity.Type.month,
                                           bound=pd.Timestamp(2022, 1, 1))

        dist = distribution.PERT(peak=5, weighting=4, minimum=2, maximum=8)
        assert isinstance(dist, distribution.Distribution)

        sums = []
        for i in range(1000):
            flow = flux.Flow.from_total(name='foo',
                                        total=dist,
                                        index=Periodicity.to_datestamps(periods),
                                        dist=distribution.Uniform(),
                                        units=currency)
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


class TestAggregation:
    flow1 = flux.Flow.from_total(name="yearly_flow",
                                 total=100.0,
                                 index=Periodicity.to_datestamps(
                                     Periodicity.period_index(include_start=pd.Timestamp(2020, 1, 31),
                                                              bound=pd.Timestamp(2022, 1, 1),
                                                              periodicity=Periodicity.Type.year)),
                                 dist=distribution.Uniform(),
                                 units=currency)

    flow2 = flux.Flow.from_total(name="weekly_flow",
                                 total=-50.0,
                                 index=Periodicity.to_datestamps(
                                     Periodicity.period_index(include_start=pd.Timestamp(2020, 3, 1),
                                                              bound=pd.Timestamp(2021, 2, 28),
                                                              periodicity=Periodicity.Type.week)),
                                 dist=distribution.Uniform(),
                                 units=currency)

    aggregation = flux.Aggregation(name="aggregation",
                                   aggregands=[flow1, flow2],
                                   periodicity=Periodicity.Type.month)

    aggregation.display()

    def test_aggregation_validity(self):
        assert TestAggregation.aggregation.name == "aggregation"
        assert len(TestAggregation.aggregation._aggregands) == 2
        assert TestAggregation.aggregation.start_date == pd.Timestamp(2020, 3, 1)
        assert TestAggregation.aggregation.end_date == pd.Timestamp(2022, 12, 31)

        TestAggregation.aggregation.display()

        assert TestAggregation.aggregation.sum().movements.index.size == 24 + 10  # Two full years plus March-Dec inclusive
        assert TestAggregation.aggregation.aggregation['weekly_flow'].sum() == -50
        assert TestAggregation.aggregation.aggregation.index.freq == 'M'

    def test_aggregation_duplication(self):
        duplicate = TestAggregation.aggregation.duplicate()
        assert duplicate.name == "aggregation"
        assert len(duplicate._aggregands) == 2
        assert duplicate.aggregation.index.freq == 'M'


class TestPhase:
    def test_correct_phase(self):
        test_phase = phase.Phase(name='test_phase',
                                 start_date=pd.Timestamp(2020, 3, 1),
                                 end_date=pd.Timestamp(2021, 2, 28))
        assert test_phase.start_date < test_phase.end_date
        assert test_phase.duration(Periodicity.Type.day) == 364

    def test_correct_phases(self):
        dates = [pd.Timestamp(2020, 2, 29),
                 pd.Timestamp(2020, 3, 1),
                 pd.Timestamp(2021, 2, 28),
                 pd.Timestamp(2021, 12, 31),
                 pd.Timestamp(2024, 2, 29)]
        names = ['Phase1', 'Phase2', 'Phase3', 'Phase4']
        phases = phase.Phase.from_date_sequence(names=names, dates=dates)

        assert len(phases) == 4
        assert phases[0].name == 'Phase1'
        assert phases[0].end_date == pd.Timestamp(2020, 2, 29)
        assert phases[0].duration(Periodicity.Type.day) == 0

        assert phases[1].start_date == pd.Timestamp(2020, 3, 1)
        assert phases[1].end_date == pd.Timestamp(2021, 2, 27)


class TestMeasures:
    aud = measure.add_currency(
        country_code='AUD',
        unit_registry=units)

    def test_currency(self):
        assert TestMeasures.aud.name == 'Australian Dollar'
        assert TestMeasures.aud.units == 'AUD'
        assert TestMeasures.aud.units.dimensionality == '[currency]'

    gfa = measure.Measure(
        name='Gross Floor Area',
        units=units.meter ** 2)

    nsa = measure.Measure(
        name='Net Sellable Area',
        units=units.meter ** 2)

    rent = measure.Measure(
        name='Rent',
        units=aud.units)

    rent_per_nsa = measure.Measure(
        name='Rent per m2 of NSA',
        units=rent.units / nsa.units)

    def test_custom_derivative(self):
        assert TestMeasures.rent_per_nsa.units == 'AUD / meter ** 2'


class TestSpace:
    parent_type = space.Type(
        name='ParentType')
    child_type = space.Type(
        name='ChildType',
        parent=parent_type)
    grandchild01_type = space.Type(
        name='Grandchild01Type')
    grandchild02_type = space.Type(
        name='Grandchild02Type')
    grandchild01_type.set_parent(child_type)
    grandchild02_type.set_parent(child_type)
    parent_type.set_children([child_type])

    def test_type_hierarchy(self):
        assert TestSpace.parent_type.children == [TestSpace.child_type]
        assert TestSpace.child_type.children == [TestSpace.grandchild01_type,
                                                 TestSpace.grandchild02_type]
        assert TestSpace.grandchild01_type.__str__() == 'ParentType.ChildType.Grandchild01Type'
        print(TestSpace.grandchild02_type)

    def test_space_init(self):
        parent_space = space.Space(
            name='Parent',
            type=TestSpace.parent_type,
            measurements={TestMeasures.gfa: 12.3 * TestMeasures.gfa.units,
                          TestMeasures.nsa: 4.56 * TestMeasures.nsa.units})

        assert parent_space.measurements[TestMeasures.gfa].units.dimensionality == '[length] ** 2'

        parent_space.measurements[TestMeasures.rent] = 9.81 * TestMeasures.rent_per_nsa.units * parent_space.measurements[TestMeasures.nsa]
        assert parent_space.measurements[TestMeasures.rent].units == 'AUD'

# plt.show(block=True)
# plt.interactive(True)
