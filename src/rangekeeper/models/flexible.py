import pandas as pd

import rangekeeper as rk


# Base Model:
class Model:
    def __init__(
            self,
            params: dict):

        # Phasing:
        self.acquisition_span = rk.span.Span.from_duration(
            name='Acquisition',
            date=params['start_date'],
            duration=rk.duration.Type.YEAR)

        self.operation_span = rk.span.Span.from_duration(
            name='Operation',
            date=rk.duration.offset(
                date=self.acquisition_span.end_date,
                duration=rk.duration.Type.DAY),
            duration=rk.duration.Type.YEAR,
            amount=params['num_periods'])

        self.disposition_span = rk.span.Span.from_duration(
            name='Disposition',
            date=rk.duration.offset(
                date=self.acquisition_span.start_date,
                duration=rk.duration.Type.YEAR,
                amount=params['num_periods']),
            duration=rk.duration.Type.YEAR)

        self.projection_span = rk.span.Span.from_duration(
            name='Projection',
            date=rk.duration.offset(
                date=self.operation_span.end_date,
                duration=rk.duration.Type.DAY),
            duration=rk.duration.Type.YEAR)

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
                sequence=self.noi_calc_span.to_sequence(frequency=params['frequency'])),
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
        self.vacancy = rk.flux.Flow.from_sequence(
            name='Vacancy Allowance',
            sequence=self.noi_calc_span.to_sequence(frequency=params['frequency']),
            data=self.pgi.movements * params['vacancy_rate'],
            units=params['units']).invert()

        # Effective Gross Income:
        self.egi = rk.flux.Stream(
            name='Effective Gross Income',
            flows=[self.pgi, self.vacancy],
            frequency=params['frequency'])

        # Operating Expenses:
        self.opex = rk.flux.Flow.from_sequence(
            name='Operating Expenses',
            sequence=self.noi_calc_span.to_sequence(frequency=params['frequency']),
            data=self.pgi.movements * params['opex_pgi_ratio'],
            units=params['units']).invert()

        # Net Operating Income:
        self.noi = rk.flux.Stream(
            name='Net Operating Income',
            flows=[self.egi.sum('Effective Gross Income'), self.opex],
            frequency=params['frequency'])

        # Capital Expenses:
        self.capex = rk.flux.Flow.from_sequence(
            name='Capital Expenditures',
            sequence=self.noi_calc_span.to_sequence(frequency=params['frequency']),
            data=self.pgi.movements * params['capex_pgi_ratio'],
            units=params['units']).invert()

        # Net Cashflows:
        self.ncf = rk.flux.Stream(
            name='Net Cashflows',
            flows=[self.noi.sum(), self.capex],
            frequency=params['frequency'])

        # Reversion:
        # We no longer need the noi_calc_span:
        operation_periods = self.operation_span.to_sequence(frequency=params['frequency'])
        self.cap_rates = params['asset_market_dist'].sample(size=operation_periods.size)
        self.sale_values = rk.flux.Flow.from_sequence(
            name='Sale Values',
            # We no longer need the noi_calc_span:
            sequence=operation_periods,
            data=list(self.ncf.sum().movements[
                      :self.operation_span.end_date] / self.cap_rates),
            units=params['units'])

        # Flexibility Rules:
        disposition_flags = []
        for i in range(self.sale_values.movements.size):
            flag = False
            if i > 1:
                if not any(disposition_flags):
                    if self.pgi_factor.movements.iloc[i] > 1.2:
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
            frequency=params['frequency'],
            discount_rate=params['discount_rate'])

        # Calculate the Present Value of Disposition CFs:
        self.pv_disposition = self.disposition.pv(
            frequency=params['frequency'],
            discount_rate=params['discount_rate'])

        self.pv_ncf_agg = rk.flux.Stream(
            name='Discounted Net Cashflow Sums',
            flows=[self.pv_ncf, self.pv_disposition],
            frequency=params['frequency'])

        self.pv_sums = self.pv_ncf_agg.sum()

        self.pv_sums.movements = self.pv_sums.movements[:self.disposition_date]

        self.acquisition = rk.flux.Flow.from_sequence(
            sequence=self.acquisition_span.to_sequence(frequency=rk.duration.Type.YEAR),
            data=[-abs(params['acquisition_price'])],
            units=params['units'],
            name='Acquisition Price')

        self.investment_cashflows = rk.flux.Stream(
            name='Investment Cashflows',
            flows=[self.ncf.sum(), self.disposition, self.acquisition],
            frequency=params['frequency'])

        self.investment_cashflows.frame = self.investment_cashflows.frame[:self.disposition_date]
        self.irr = self.investment_cashflows.sum().xirr()
        self.npv = self.investment_cashflows.sum().xnpv(params['discount_rate'])
