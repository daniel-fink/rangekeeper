import pandas as pd

import rangekeeper as rk

# except:
#     import modules.rangekeeper.distribution
#     from modules.rangekeeper.flux import Flow, Confluence
#     from modules.rangekeeper.periodicity import Periodicity
#     from modules.rangekeeper.phase import Phase


# Base Model:
class Model:
    def __init__(
            self,
            params: dict):

        # Phasing:
        self.acquisition_phase = rk.phase.Phase.from_num_periods(
            name='Acquisition',
            date=params['start_date'],
            period_type=rk.periodicity.Type.year,
            num_periods=1)

        self.operation_phase = rk.phase.Phase.from_num_periods(
            name='Operation',
            date=rk.periodicity.date_offset(
                date=self.acquisition_phase.end_date,
                period_type=rk.periodicity.Type.day,
                num_periods=1),
            period_type=rk.periodicity.Type.year,
            num_periods=params['num_periods'])

        self.projection_phase = rk.phase.Phase.from_num_periods(
            name='Projection',
            date=rk.periodicity.date_offset(
                date=self.operation_phase.end_date,
                period_type=rk.periodicity.Type.day,
                num_periods=1),
            period_type=rk.periodicity.Type.year,
            num_periods=1)

        self.noi_calc_phase = rk.phase.Phase.merge(
            name='NOI Calculation Phase',
            phases=[self.operation_phase, self.projection_phase])

        # Cashflows:
        self.escalation = rk.projection.Extrapolation.Compounding(rate=params['growth_rate'])

        # Potential Gross Income
        self.pgi = rk.flux.Flow.from_projection(
            name='Potential Gross Income',
            value=params['initial_pgi'],
            proj=rk.projection.Extrapolation(
                form=self.escalation,
                sequence=self.noi_calc_phase.to_index(period_type=params['period_type'])),
            units=params['units'])

        self.addl_pgi = rk.flux.Flow(
            movements=pd.Series(
                data=range(self.pgi.movements.size),
                index=self.pgi.movements.index,
                dtype=float),
            units=params['units'],
            name='Additional PGI')

        self.addl_pgi.movements = self.addl_pgi.movements * params['addl_pgi_per_period']
        self.pgi = rk.flux.Flow(
            movements=self.pgi.movements + self.addl_pgi.movements,
            units=params['units'],
            name=self.pgi.name)

        # Vacancy Allowance
        self.vacancy = rk.flux.Flow.from_periods(
            name='Vacancy Allowance',
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['vacancy_rate'],
            units=params['units']).invert()

        # Effective Gross Income:
        self.egi = rk.flux.Confluence(
            name='Effective Gross Income',
            affluents=[self.pgi, self.vacancy],
            period_type=params['period_type'])

        # Operating Expenses:
        self.opex = rk.flux.Flow.from_periods(
            name='Operating Expenses',
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['opex_pgi_ratio'],
            units=params['units']).invert()

        # Net Operating Income:
        self.noi = rk.flux.Confluence(
            name='Net Operating Income',
            affluents=[self.egi.sum('Effective Gross Income'), self.opex],
            period_type=params['period_type'])

        # Capital Expenses:
        self.capex = rk.flux.Flow.from_periods(
            name='Capital Expenditures',
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['capex_pgi_ratio'],
            units=params['units']).invert()

        # Net Cashflows:
        self.ncf = rk.flux.Confluence(
            name='Net Cashflows',
            affluents=[self.noi.sum(), self.capex],
            period_type=params['period_type'])

        # Disposition
        # We require each next period's NCF as the numerator:
        sale_values = list(self.ncf.sum().movements.iloc[1:] / params['cap_rate'])
        self.disposition = rk.flux.Flow.from_periods(
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
        pv_ncf_cumsum = rk.flux.Flow(
            movements=self.pv_ncf.movements.cumsum(),
            name='Discounted Net Cashflow Cumulative Sums',
            units=params['units'])
        self.pv_ncf_agg = rk.flux.Confluence(
            name='Discounted Net Cashflow Sums',
            affluents=[pv_ncf_cumsum, self.pv_disposition],
            period_type=params['period_type'])

        self.pv_sums = self.pv_ncf_agg.sum()
        self.pv_sums.movements = self.pv_sums.movements[:-1]
