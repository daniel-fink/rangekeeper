import pandas as pd

# try:
import projection
import distribution
from flux import Flow, Aggregation
import periodicity
from phase import Phase


# except:
#     import modules.rangekeeper.distribution
#     from modules.rangekeeper.flux import Flow, Aggregation
#     from modules.rangekeeper.periodicity import Periodicity
#     from modules.rangekeeper.phase import Phase


# Base Model:
class Model:
    def __init__(
            self,
            params: dict):

        # Phasing:
        self.acquisition_phase = Phase.from_num_periods(
            name='Acquisition',
            start_date=params['start_date'],
            period_type=periodicity.Type.year,
            num_periods=1)

        self.operation_phase = Phase.from_num_periods(
            name='Operation',
            start_date=periodicity.date_offset(
                date=self.acquisition_phase.end_date,
                period_type=periodicity.Type.day,
                num_periods=1),
            period_type=periodicity.Type.year,
            num_periods=params['num_periods'])

        self.projection_phase = Phase.from_num_periods(
            name='Projection',
            start_date=periodicity.date_offset(
                date=self.operation_phase.end_date,
                period_type=periodicity.Type.day,
                num_periods=1),
            period_type=periodicity.Type.year,
            num_periods=1)

        self.noi_calc_phase = Phase.merge(
            name='NOI Calculation Phase',
            phases=[self.operation_phase, self.projection_phase])

        # Cashflows:
        self.escalation = projection.Exponential(rate=params['growth_rate'])

        # Potential Gross Income
        self.pgi = Flow.from_projection(
            name='Potential Gross Income',
            value=params['initial_pgi'],
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            proj=self.escalation,
            units=params['units'])

        self.addl_pgi = Flow(
            movements=pd.Series(
                data=range(self.pgi.movements.size),
                index=self.pgi.movements.index,
                dtype=float),
            units=params['units'],
            name='Additional PGI')

        self.addl_pgi.movements = self.addl_pgi.movements * params['addl_pgi_per_period']
        self.pgi = Flow(
            movements=self.pgi.movements + self.addl_pgi.movements,
            units=params['units'],
            name=self.pgi.name)

        # Vacancy Allowance
        self.vacancy = Flow.from_periods(
            name='Vacancy Allowance',
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['vacancy_rate'],
            units=params['units']).invert()

        # Effective Gross Income:
        self.egi = Aggregation(
            name='Effective Gross Income',
            aggregands=[self.pgi, self.vacancy],
            period_type=params['period_type'])

        # Operating Expenses:
        self.opex = Flow.from_periods(
            name='Operating Expenses',
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['opex_pgi_ratio'],
            units=params['units']).invert()

        # Net Operating Income:
        self.noi = Aggregation(
            name='Net Operating Income',
            aggregands=[self.egi.sum('Effective Gross Income'), self.opex],
            period_type=params['period_type'])

        # Capital Expenses:
        self.capex = Flow.from_periods(
            name='Capital Expenditures',
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['capex_pgi_ratio'],
            units=params['units']).invert()

        # Net Cashflows:
        self.ncf = Aggregation(
            name='Net Cashflows',
            aggregands=[self.noi.sum(), self.capex],
            period_type=params['period_type'])

        # Disposition
        # We require each next period's NCF as the numerator:
        sale_values = list(self.ncf.sum().movements.iloc[1:] / params['cap_rate'])
        self.disposition = Flow.from_periods(
            name='Disposition',
            # We no longer need the noi_calc_phase:
            index=self.operation_phase.to_index(period_type=params['period_type']),
            data=sale_values,
            units=params['units'])

        # Calculate the Present Value of the NCFs:
        self.pv_ncf = self.ncf.sum().pv(
            period_type=params['period_type'],
            discount_rate=params['discount_rate'])

        # Calculate the Present Value of Reversion CFs:
        self.pv_disposition = self.disposition.pv(
            period_type=params['period_type'],
            discount_rate=params['discount_rate'])

        # Add Cumulative Sum of Discounted Net Cashflows to each period's Discounted Disposition
        pv_ncf_cumsum = Flow(
            movements=self.pv_ncf.movements.cumsum(),
            name='Discounted Net Cashflow Cumulative Sums',
            units=params['units'])
        self.pv_ncf_agg = Aggregation(
            name='Discounted Net Cashflow Sums',
            aggregands=[pv_ncf_cumsum, self.pv_disposition],
            period_type=params['period_type'])

        self.pv_sums = self.pv_ncf_agg.sum()
        self.pv_sums.movements = self.pv_sums.movements[:-1]
