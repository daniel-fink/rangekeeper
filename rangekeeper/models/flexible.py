import pandas as pd

import rangekeeper as rk


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

        self.disposition_span = rk.span.Span.from_num_periods(
            name='Disposition',
            date=rk.periodicity.offset_date(
                date=self.acquisition_span.start_date,
                period_type=rk.periodicity.Type.YEAR,
                num_periods=params['num_periods']),
            period_type=rk.periodicity.Type.YEAR,
            num_periods=1)

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

        factors = params['space_market_dist'].sample(size=self.pgi.movements.size)
        self.pgi_factor = rk.flux.Flow(
            movements=pd.Series(
                data=factors,
                index=self.pgi.movements.index,
                dtype=float),
            units=params['units'],
            name='Space Market Pricing Factors')

        self.pgi = rk.flux.Flow(
            movements=self.pgi.movements * self.pgi_factor.movements,
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

        # Reversion:
        # We no longer need the noi_calc_span:
        operation_periods = self.operation_span.to_index(period_type=params['period_type'])
        self.cap_rates = params['asset_market_dist'].sample(size=operation_periods.size)
        self.sale_values = rk.flux.Flow.from_periods(
            name='Sale Values',
            # We no longer need the noi_calc_span:
            index=operation_periods,
            data=list(self.ncf.sum().movements[
                      :self.operation_span.end_date] / self.cap_rates),
            units=params['units'])

        # Flexibility Rules:
        disposition_flags = []
        for i in range(self.sale_values.movements.size):
            flag = False
            if i > 1:
                if not any(disposition_flags):
                    if self.pgi_factor.movements[i] > 1.2:
                        self.disposition_date = self.sale_values.movements.index[i]
                        flag = True
            disposition_flags.append(flag)

        self.disposition = rk.flux.Flow(
            name="Disposition",
            movements=pd.Series(
                data=self.sale_values.movements * disposition_flags,
                index=self.sale_values.movements.index),
            units=params['units'])

        # Calculate the Present Value of the NCFs:
        self.pv_ncf = self.ncf.sum().pv(
            period_type=params['period_type'],
            discount_rate=params['discount_rate'])

        # Calculate the Present Value of Disposition CFs:
        self.pv_disposition = self.disposition.pv(
            period_type=params['period_type'],
            discount_rate=params['discount_rate'])

        self.pv_ncf_agg = rk.flux.Stream(
            name='Discounted Net Cashflow Sums',
            flows=[self.pv_ncf, self.pv_disposition],
            period_type=params['period_type'])

        self.pv_sums = self.pv_ncf_agg.sum()

        self.pv_sums.movements = self.pv_sums.movements[:self.disposition_date]

        self.acquisition = rk.flux.Flow.from_periods(
            index=self.acquisition_span.to_index(rk.periodicity.Type.YEAR),
            data=[-abs(params['acquisition_price'])],
            units=params['units'],
            name='Acquisition Price')

        self.investment_cashflows = rk.flux.Stream(
            name='Investment Cashflows',
            flows=[self.ncf.sum(), self.disposition, self.acquisition],
            period_type=params['period_type'])

        self.investment_cashflows.frame = self.investment_cashflows.frame[:self.disposition_date]
        self.irr = self.investment_cashflows.sum().xirr()
        self.npv = self.investment_cashflows.sum().xnpv(params['discount_rate'])
