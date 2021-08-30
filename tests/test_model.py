import pytest
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

import modules.distribution
import modules.flux
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
    #print(len(parameters))

    def test_correct_distributions(self):
        uniform_dist = modules.distribution.Uniform()
        uniform_densities = uniform_dist.interval_density(parameters=TestDistribution.parameters)
        #plt.plot(TestDistribution.parameters, uniform_densities)
        assert sum(uniform_densities) == 1.0

        exp_dist = modules.distribution.Exponential(rate=0.02, num_periods=12)
        # exp_factors = exp_dist.factor(parameters=parameters)
        exp_densities = exp_dist.density(parameters=TestDistribution.parameters)
        exp_cumulative = exp_dist.cumulative_density(parameters=TestDistribution.parameters)

        #plt.plot(parameters, exp_factors)
        plt.plot(TestDistribution.parameters, exp_densities)
        plt.plot(TestDistribution.parameters, exp_cumulative)
        # assert exp_factors[100 - 1] == math.pow((1 + 0.02), 100)

    def test_correct_PERT_dist(self):
        pert_dist = modules.distribution.PERT(peak=0.75, weighting=4)
        pert_values = pert_dist.interval_density(parameters=TestDistribution.parameters)
        #plt.plot(TestDistribution.parameters, pert_values)
        #print("PERT CDF: " + str(pert_values))
        assert sum(pert_values) == 1.0

        # print(pert_value)

        #plt.show(block=True)
        #plt.interactive(True)


class TestPeriod:
    def test_correct_periods(self):
        date = pd.Timestamp(2020, 2, 28)
        period = Periodicity.include_date(date=date, duration=Periodicity.Type.month)
        assert period.day == 29  # end date of Period
        assert period.month == 2

        sequence = Periodicity.period_sequence(date, pd.Timestamp(2020, 12, 31), Periodicity.Type.quarter)
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
    flow_from_series = modules.flux.Flow(movements=series, units=Units.Type.USD)

    dict = {date1: values[0], date2: values[1], date3: values[2]}
    flow_from_dict = modules.flux.Flow.from_dict(movements=dict, name="foo", units=Units.Type.USD)

    def test_correct_flow(self):
        date = pd.Timestamp(2000, 2, 29)
        assert TestFlow.flow_from_series.movements[date] == 2.3
        assert TestFlow.flow_from_series.movements.size == 3
        assert TestFlow.flow_from_series.movements.loc[date] == 2.3
        assert TestFlow.flow_from_series.movements.equals(TestFlow.flow_from_dict.movements)
        assert isinstance(TestFlow.flow_from_series.movements.index, pd.DatetimeIndex)

    periods = Periodicity.period_sequence(include_start=pd.Timestamp(2020, 1, 31),
                                          include_end=pd.Timestamp(2022, 1, 1),
                                          periodicity=Periodicity.Type.month)

    sum_flow = modules.flux.Flow.from_total(name="bar",
                                            total=100.0,
                                            index=periods,
                                            distribution=modules.distribution.Uniform(),
                                            units=Units.Type.USD)
    # print(sum_flow.movements)

    invert_flow = sum_flow.invert()

    def test_correct_sumflow(self):
        assert TestFlow.sum_flow.movements.size == 25
        assert TestFlow.sum_flow.movements.array.sum() == 100.0
        assert TestFlow.sum_flow.movements.index.array[1] == pd.Timestamp(2020, 2, 29)
        assert TestFlow.sum_flow.movements.array[1] == 4
        assert TestFlow.sum_flow.movements.name == "bar"
        assert TestFlow.sum_flow.units == Units.Type.USD

    def test_correct_invert(self):
        assert TestFlow.invert_flow.movements.size == 25
        assert TestFlow.invert_flow.movements.array.sum() == -100.0
        assert TestFlow.invert_flow.movements.index.array[2] == pd.Timestamp(2020, 3, 31)
        assert TestFlow.invert_flow.movements.array[2] == -4
        assert TestFlow.invert_flow.movements.name == "bar"
        assert TestFlow.invert_flow.units == Units.Type.USD

    resample_flow = invert_flow.resample(periodicity_type=Periodicity.Type.year)

    def test_correct_resample(self):
        assert TestFlow.resample_flow.movements.size == 3
        assert TestFlow.resample_flow.movements[0] == -48
        assert TestFlow.resample_flow.movements[1] == -48
        assert TestFlow.resample_flow.movements[2] == -4


class TestConfluence:
    flow1 = modules.flux.Flow.from_total(name="yearly_flow",
                                         total=100.0,
                                         index=Periodicity.period_sequence(
                                             include_start=pd.Timestamp(2020, 1, 31),
                                             include_end=pd.Timestamp(2022, 1, 1),
                                             periodicity=Periodicity.Type.year),
                                         distribution=modules.distribution.Uniform(),
                                         units=Units.Type.USD)

    flow2 = modules.flux.Flow.from_total(name="weekly_flow",
                                         total=-50.0,
                                         index=Periodicity.period_sequence(include_start=pd.Timestamp(2020, 3, 1),
                                                                           include_end=pd.Timestamp(2021, 2, 28),
                                                                           periodicity=Periodicity.Type.week),
                                         distribution=modules.distribution.Uniform(),
                                         units=Units.Type.USD)

    confluence = modules.flux.Confluence(name="confluence",
                                         affluents=[flow1, flow2],
                                         periodicity_type=Periodicity.Type.month)

    def test_correct_confluence(self):
        assert TestConfluence.confluence.name == "confluence"
        assert len(TestConfluence.confluence._affluents) == 2
        assert TestConfluence.confluence.start_date == pd.Timestamp(2020, 3, 1)
        assert TestConfluence.confluence.end_date == pd.Timestamp(2022, 12, 31)
        assert TestConfluence.confluence.sum().movements.index.size == 24 + 10  # Two full years plus March-Dec inclusive
        assert TestConfluence.confluence.confluence['weekly_flow'].sum() == -50
        assert TestConfluence.confluence.confluence.index.freq == 'M'


class TestBaselineProforma:
    project_start = pd.Timestamp(2021, 1, 1)
    project_end = project_start + pd.offsets.YearEnd(10)

    gfa = 100
    initial_rent_psf_pa = 1

    # Revenues:
    periods = Periodicity.period_sequence(include_start=project_start,
                                          include_end=project_end,
                                          periodicity=Periodicity.Type.year)

    pgi_unesc = modules.flux.Flow.from_total(name='pgi',
                                             total=gfa * initial_rent_psf_pa * periods.size,
                                             index=periods,
                                             distribution=modules.distribution.Uniform(),
                                             units=Units.Type.USD)
    pgi_esc = modules.flux.Flow.from_initial(name='pgi_esc',
                                             initial=gfa * initial_rent_psf_pa,
                                             index=periods,
                                             distribution=modules.distribution.Exponential(0.02, periods.size),
                                             units=Units.Type.USD)
    pgi_esc = modules.flux.Flow(pgi_esc.movements - (gfa * initial_rent_psf_pa), units=Units.Type.USD,
                                name='pgi_unesc')
    pgi = modules.flux.Confluence(name='pgi', affluents=[pgi_unesc, pgi_esc], periodicity_type=Periodicity.Type.year)

    # Vacancy:
    vacancy = modules.flux.Flow(pgi.sum().movements * 0.05, units=Units.Type.USD, name='vacancy').invert()
    print(vacancy.movements)

    # Effective Gross Income
    egi = modules.flux.Confluence('egi', [pgi.sum(), vacancy], Periodicity.Type.year)
    print(egi.sum().movements)

    # pgi_esc = modules.flow.Flow.

    # print(pgi.movements)

    # construction_start = project_start
    # construction_end = construction_start + pd.offsets.MonthEnd(24)
    #
    # absorption_start = construction_end
    # absorption_end = absorption_start + pd.offsets.MonthEnd(18)
    #
    # stabilization_start = absorption_end
    # stabilization_end = absorption_end + pd.offsets.YearEnd(12)
    #
    # disposition_start = stabilization_end
    # disposition_end = disposition_start + pd.offsets.MonthEnd(6)
