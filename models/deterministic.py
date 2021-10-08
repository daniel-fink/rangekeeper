import math
import pandas as pd
import numpy_financial as npf

import modules.distribution
from modules.flux import Flow, Aggregation
from modules.units import Units
from modules.periodicity import Periodicity
from modules.distribution import Type, Uniform, Exponential
from modules.phase import Phase


# Base Model:
class Model:
    def __init__(self, params: dict):
        # Phasing:
        self.acquisition_phase = Phase.from_num_periods(name='Acquisition',
                                                        start_date=params['start_date'],
                                                        period_type=Periodicity.Type.year,
                                                        num_periods=1)

        self.operation_phase = Phase.from_num_periods(name='Operation',
                                                      start_date=Periodicity.date_offset(
                                                          date=self.acquisition_phase.end_date,
                                                          period_type=Periodicity.Type.day,
                                                          num_periods=1),
                                                      period_type=Periodicity.Type.year,
                                                      num_periods=params['num_periods'])

        self.projection_phase = Phase.from_num_periods(name='Projection',
                                                       start_date=Periodicity.date_offset(
                                                           date=self.operation_phase.end_date,
                                                           period_type=Periodicity.Type.day,
                                                           num_periods=1),
                                                       period_type=Periodicity.Type.year,
                                                       num_periods=1)

        self.noi_calc_phase = Phase.merge(name='NOI Calculation Phase',
                                          phases=[self.operation_phase, self.projection_phase])

        # Cashflows:
        self.distribution = modules.distribution.Exponential(rate=params['growth_rate'],
                                                             num_periods=self.noi_calc_phase.duration(
                                                                 period_type=params['period_type'],
                                                                 inclusive=True))

        # Potential Gross Income
        self.pgi = Flow.from_initial(name='Potential Gross Income',
                                     initial=params['initial_pgi'],
                                     index=self.noi_calc_phase.to_index(periodicity=params['period_type']),
                                     distribution=Exponential(rate=params['growth_rate'],
                                                              num_periods=self.noi_calc_phase.duration(
                                                                  period_type=params['period_type'],
                                                                  inclusive=True)),
                                     units=params['units'])

        self.addl_pgi = Flow(data=pd.Series(data=range(self.pgi.size),
                                            index=self.pgi.index,
                                            dtype=float),
                             units=params['units'],
                             name='Additional PGI')

        self.addl_pgi = self.addl_pgi * params['addl_pgi_per_period']
        self.pgi = Flow(data=self.pgi + self.addl_pgi,
                        units=params['units'],
                        name=self.pgi.name)

        # Vacancy Allowance
        self.vacancy = Flow.from_periods(name='Vacancy Allowance',
                                         periods=self.noi_calc_phase.to_index(periodicity=params['period_type']),
                                         data=self.pgi * params['vacancy_rate'],
                                         units=params['units']).invert()

        # Effective Gross Income:
        self.egi = Aggregation(name='Effective Gross Income',
                               aggregands=[self.pgi, self.vacancy],
                               periodicity_type=params['period_type'])

        # Operating Expenses:
        self.opex = Flow.from_periods(name='Operating Expenses',
                                      periods=self.noi_calc_phase.to_index(periodicity=params['period_type']),
                                      data=self.pgi * params['opex_pgi_ratio'],
                                      units=params['units']).invert()

        # Net Operating Income:
        self.noi = Aggregation(name='Net Operating Income',
                               aggregands=[self.egi.sum('Effective Gross Income'), self.opex],
                               periodicity_type=params['period_type'])

        # Capital Expenses:
        self.capex = Flow.from_periods(name='Capital Expenditures',
                                       periods=self.noi_calc_phase.to_index(periodicity=params['period_type']),
                                       data=self.pgi * params['capex_pgi_ratio'],
                                       units=params['units']).invert()

        # Net Cashflows:
        self.ncf = Aggregation(name='Net Cashflows',
                               aggregands=[self.noi.sum(), self.capex],
                               periodicity_type=params['period_type'])

        # Reversion:
        # We require each next period's NCF as the numerator:
        sale_values = list(self.ncf.sum().iloc[1:] / params['cap_rate'])
        self.reversion = Flow.from_periods(name='Reversion',
                                           # We no longer need the noi_calc_phase:
                                           periods=self.operation_phase.to_index(periodicity=params['period_type']),
                                           data=sale_values,
                                           units=params['units'])

        # Calculate the Present Value of the NCFs:
        self.pv_ncf = self.ncf.sum().pv(periodicity=params['period_type'],
                                        discount_rate=params['discount_rate'])

        # Calculate the Present Value of Reversion CFs:
        self.pv_reversion = self.reversion.pv(periodicity=params['period_type'],
                                              discount_rate=params['discount_rate'])

        # Add Cumulative Sum of Discounted Net Cashflows to each period's Discounted Reversion:
        pv_ncf_cumsum = Flow(data=self.pv_ncf.cumsum(),
                             name='Discounted Net Cashflow Cumulative Sums',
                             units=params['units'])
        self.pv_ncf_agg = Aggregation(name='Discounted Net Cashflow Sums',
                                      aggregands=[pv_ncf_cumsum, self.pv_reversion],
                                      periodicity_type=params['period_type'])

        self.pv_sums = self.pv_ncf_agg.sum()
        self.pv_sums = Flow(data=self.pv_sums[:-1], units=self.pv_sums.name)



