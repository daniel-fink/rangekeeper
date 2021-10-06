import pytest
import pandas as pd
import numpy as np
import scipy.stats as ss
import matplotlib
import matplotlib.pyplot as plt

import modules.distribution
import modules.flux
import modules.phase
from modules.units import Units
from modules.periodicity import Periodicity

# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.

matplotlib.use('TkAgg')
plt.style.use('seaborn')  # pretty matplotlib plots
plt.rcParams['figure.figsize'] = (12, 8)


class TestDistribution:
    num_periods = 100
    parameters = np.linspace(0, 1, num=num_periods)

    # print(len(parameters))

    def test_uniform_distribution_has_density_of_1(self):
        uniform_dist = modules.distribution.Uniform(generator=None)
        uniform_densities = uniform_dist.interval_density(parameters=TestDistribution.parameters)
        # plt.plot(TestDistribution.parameters, uniform_densities)
        assert sum(uniform_densities) == 1.0

    def test_exponential_distribution_total_and_initial_match(self):
        exp_dist = modules.distribution.Exponential(rate=0.02, num_periods=12)
        # exp_factors = exp_dist.factor(parameters=parameters)
        exp_densities = exp_dist.density(parameters=TestDistribution.parameters)
        exp_cumulative = exp_dist.cumulative_density(parameters=TestDistribution.parameters)

        # plt.plot(parameters, exp_factors)
        # plt.plot(TestDistribution.parameters, exp_densities)
        # plt.plot(TestDistribution.parameters, exp_cumulative)
        # assert exp_factors[100 - 1] == math.pow((1 + 0.02), 100)

    def test_PERT_distribution_sums_to_1(self):
        pert_dist = modules.distribution.PERT(peak=0.75, weighting=4)
        pert_values = pert_dist.interval_density(parameters=TestDistribution.parameters)
        # plt.plot(TestDistribution.parameters, pert_values)
        # print("PERT CDF: " + str(pert_values))
        assert sum(pert_values) == 1.0

        # print(pert_value)


class TestPeriod:
    def test_correct_periods(self):
        date = pd.Timestamp(2020, 2, 28)
        period = Periodicity.include_date(date=date, duration=Periodicity.Type.month)
        assert period.day == 29  # end date of Period
        assert period.month == 2

        sequence = Periodicity.period_sequence(include_start=date,
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
    flow_from_series = modules.flux.Flow(data=series, units=Units.Type.USD)

    dict = {date1: values[0], date2: values[1], date3: values[2]}
    flow_from_dict = modules.flux.Flow.from_dict(data=dict, name="foo", units=Units.Type.USD)

    def test_correct_flow(self):
        # TestFlow.flow_from_series.display()
        # TestFlow.flow_from_dict.display()
        date = pd.Timestamp(2000, 2, 29)
        assert TestFlow.flow_from_series[date] == 2.3
        assert TestFlow.flow_from_series.size == 3
        assert TestFlow.flow_from_series.loc[date] == 2.3
        assert TestFlow.flow_from_series.equals(TestFlow.flow_from_dict)
        assert isinstance(TestFlow.flow_from_series.index, pd.DatetimeIndex)

    periods = Periodicity.period_sequence(include_start=pd.Timestamp(2020, 1, 31),
                                          periodicity=Periodicity.Type.month,
                                          bound=pd.Timestamp(2022, 1, 1))

    sum_flow = modules.flux.Flow.from_total(name="bar",
                                            total=100.0,
                                            index=periods,
                                            distribution=modules.distribution.Uniform(),
                                            units=Units.Type.USD)

    invert_flow = sum_flow.invert()

    def test_correct_sumflow(self):
        # TestFlow.sum_flow.display()
        assert TestFlow.sum_flow.size == 25
        assert TestFlow.sum_flow.array.sum() == 100.0
        assert TestFlow.sum_flow.index.array[1] == pd.Timestamp(2020, 2, 29)
        assert TestFlow.sum_flow.array[1] == 4
        assert TestFlow.sum_flow.name == "bar"
        assert TestFlow.sum_flow.units == Units.Type.USD

    def test_correct_invert(self):
        # TestFlow.invert_flow.display()
        assert TestFlow.invert_flow.size == 25
        assert TestFlow.invert_flow.array.sum() == -100.0
        assert TestFlow.invert_flow.index.array[2] == pd.Timestamp(2020, 3, 31)
        assert TestFlow.invert_flow.array[2] == -4
        assert TestFlow.invert_flow.name == "bar"
        assert TestFlow.invert_flow.units == Units.Type.USD

    resample_flow = invert_flow.resample(periodicity_type=Periodicity.Type.year)

    def test_correct_resample(self):
        # TestFlow.resample_flow.display()
        assert TestFlow.resample_flow.size == 3
        assert TestFlow.resample_flow[0] == -48
        assert TestFlow.resample_flow[1] == -48
        assert TestFlow.resample_flow[2] == -4

    def test_distribution_as_input(self):
        periods = Periodicity.period_sequence(include_start=pd.Timestamp(2020, 1, 31),
                                              periodicity=Periodicity.Type.month,
                                              bound=pd.Timestamp(2022, 1, 1))

        dist = modules.distribution.PERT(peak=5, weighting=4, minimum=2, maximum=8)
        assert isinstance(dist, modules.distribution.Distribution)

        sums = []
        for i in range(1000):
            flow = modules.flux.Flow.from_total(name='foo',
                                                total=dist,
                                                index=periods,
                                                distribution=modules.distribution.Uniform(),
                                                units=Units.Type.AUD)
            sums.append(flow.collapse()[0])

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
    flow1 = modules.flux.Flow.from_total(name="yearly_flow",
                                         total=100.0,
                                         index=Periodicity.period_sequence(include_start=pd.Timestamp(2020, 1, 31),
                                                                           bound=pd.Timestamp(2022, 1, 1),
                                                                           periodicity=Periodicity.Type.year),
                                         distribution=modules.distribution.Uniform(),
                                         units=Units.Type.USD)

    flow2 = modules.flux.Flow.from_total(name="weekly_flow",
                                         total=-50.0,
                                         index=Periodicity.period_sequence(include_start=pd.Timestamp(2020, 3, 1),
                                                                           bound=pd.Timestamp(2021, 2, 28),
                                                                           periodicity=Periodicity.Type.week),
                                         distribution=modules.distribution.Uniform(),
                                         units=Units.Type.USD)

    aggregation = modules.flux.Aggregation(name="aggregation",
                                           aggregands=[flow1, flow2],
                                           periodicity_type=Periodicity.Type.month)

    def test_correct_aggregation(self):
        assert TestAggregation.aggregation.name == "aggregation"
        assert len(TestAggregation.aggregation._aggregands) == 2
        assert TestAggregation.aggregation.start_date == pd.Timestamp(2020, 3, 1)
        assert TestAggregation.aggregation.end_date == pd.Timestamp(2022, 12, 31)
        assert TestAggregation.aggregation.sum().index.size == 24 + 10  # Two full years plus March-Dec inclusive
        assert TestAggregation.aggregation.aggregation['weekly_flow'].sum() == -50
        assert TestAggregation.aggregation.aggregation.index.freq == 'M'


class TestPhase:
    def test_correct_phase(self):
        phase = modules.phase.Phase(name='test_phase', start_date=pd.Timestamp(2020, 3, 1),
                                    end_date=pd.Timestamp(2021, 2, 28))
        assert phase.start_date < phase.end_date
        assert phase.duration(Periodicity.Type.day) == 364

    def test_correct_phases(self):
        dates = [pd.Timestamp(2020, 2, 29), pd.Timestamp(2020, 3, 1), pd.Timestamp(2021, 2, 28),
                 pd.Timestamp(2021, 12, 31), pd.Timestamp(2024, 2, 29)]
        names = ['Phase1', 'Phase2', 'Phase3', 'Phase4']
        phases = modules.phase.Phase.from_date_sequence(names=names, dates=dates)

        assert len(phases) == 4
        assert phases[0].name == 'Phase1'
        assert phases[0].end_date == pd.Timestamp(2020, 2, 29)
        assert phases[0].duration(Periodicity.Type.day) == 0

        assert phases[1].start_date == pd.Timestamp(2020, 3, 1)
        assert phases[1].end_date == pd.Timestamp(2021, 2, 27)


# plt.show(block=True)
# plt.interactive(True)
