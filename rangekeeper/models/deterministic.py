import pandas as pd

import rangekeeper as rk

# except:
#     import modules.rangekeeper.distribution
#     from modules.rangekeeper.flux import Flow, Stream
#     from modules.rangekeeper.periodicity import Periodicity
#     from modules.rangekeeper.span import Span


# Base Model:
class Model:
    def __init__(
            self,
            params: dict):

        # Phasing:
        self.acquisition_span = rk.span.Span.from_num_periods(
            name='Acquisition',
            date=params['start_date'],
            period_type=rk.periodicity.Type.YEAR,
            num_periods=1)

        self.operation_span = rk.span.Span.from_num_periods(
            name='Operation',
            date=rk.periodicity.offset_date(
                date=self.acquisition_span.end_date,
                period_type=rk.periodicity.Type.DAY,
                num_periods=1),
            period_type=rk.periodicity.Type.YEAR,
            num_periods=params['num_periods'])

        self.projection_span = rk.span.Span.from_num_periods(
            name='Projection',
            date=rk.periodicity.offset_date(
                date=self.operation_span.end_date,
                period_type=rk.periodicity.Type.DAY,
                num_periods=1),
            period_type=rk.periodicity.Type.YEAR,
            num_periods=1)

        self.noi_calc_span = rk.span.Span.merge(
            name='NOI Calculation Span',
            spans=[self.operation_span, self.projection_span])

        # Cashflows:
        self.escalation = rk.extrapolation.Compounding(rate=params['growth_rate'])

        # Potential Gross Income
        self.pgi = rk.flux.Flow.from_projection(
            name='Potential Gross Income',
            value=params['initial_pgi'],
            proj=rk.projection.Extrapolation(
                form=self.escalation,
                sequence=self.noi_calc_span.to_index(period_type=params['period_type'])),
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
            index=self.noi_calc_span.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['vacancy_rate'],
            units=params['units']).invert()

        # Effective Gross Income:
        self.egi = rk.flux.Stream(
            name='Effective Gross Income',
            flows=[self.pgi, self.vacancy],
            period_type=params['period_type'])

        # Operating Expenses:
        self.opex = rk.flux.Flow.from_periods(
            name='Operating Expenses',
            index=self.noi_calc_span.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['opex_pgi_ratio'],
            units=params['units']).invert()

        # Net Operating Income:
        self.noi = rk.flux.Stream(
            name='Net Operating Income',
            flows=[self.egi.sum('Effective Gross Income'), self.opex],
            period_type=params['period_type'])

        # Capital Expenses:
        self.capex = rk.flux.Flow.from_periods(
            name='Capital Expenditures',
            index=self.noi_calc_span.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['capex_pgi_ratio'],
            units=params['units']).invert()

        # Net Cashflows:
        self.ncf = rk.flux.Stream(
            name='Net Cashflows',
            flows=[self.noi.sum(), self.capex],
            period_type=params['period_type'])

        # Disposition
        # We require each next period's NCF as the numerator:
        sale_values = list(self.ncf.sum().movements.iloc[1:] / params['cap_rate'])
        self.disposition = rk.flux.Flow.from_periods(
            name='Disposition',
            # We no longer need the noi_calc_span:
            index=self.operation_span.to_index(period_type=params['period_type']),
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
        self.pv_ncf_agg = rk.flux.Stream(
            name='Discounted Net Cashflow Sums',
            flows=[pv_ncf_cumsum, self.pv_disposition],
            period_type=params['period_type'])

        self.pv_sums = self.pv_ncf_agg.sum()
        self.pv_sums.movements = self.pv_sums.movements[:-1]
