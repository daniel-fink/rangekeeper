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

        # Factors:
        self.escalation = rk.extrapolation.Compounding(rate=params['growth_rate'])

        # Cashflows:
        # Potential Gross Income
        self.pgi = rk.flux.Flow.from_projection(
            name='Potential Gross Income',
            value=params['initial_pgi'],
            proj=rk.projection.Extrapolation(
                form=self.escalation,
                sequence=self.noi_calc_span.to_index(period_type=params['period_type'])),
            units=params['units'])

        # Vacancy Allowance
        # This should be displayed as a row in a table with xxxx, xxx,....
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

        # Disposition (Reversion):
        sale_value = self.ncf.sum().movements.tail(1).item() / params['cap_rate']
        self.disposition = rk.flux.Flow.from_periods(
            name='Disposition',
            index=self.disposition_span.to_index(period_type=params['period_type']),
            data=[sale_value],
            units=params['units'])

        # Net Cash Flows with Disposition:
        self.ncf_disposition = self.ncf.duplicate().trim_to_span(self.operation_span)
        self.ncf_disposition.append(flows=[self.disposition])

        # Calculate the Present Value of the NCFs:
        self.pv_ncf = self.ncf.sum().pv(
            period_type=params['period_type'],
            discount_rate=params['discount_rate'])

        # Calculate the Present Value of Disposition CFs:
        self.pv_disposition = self.disposition.pv(
            period_type=params['period_type'],
            discount_rate=params['discount_rate'])

        self.pv_ncf_agg = rk.flux.Stream(
            name='Discounted Net Cashflows',
            flows=[self.pv_ncf, self.pv_disposition],
            period_type=params['period_type'])

        self.pv_sums = self.pv_ncf_agg.sum()
        self.pv_sums.movements = self.pv_sums.movements[:-1]

        self.acquisition = rk.flux.Flow.from_periods(
            index=self.acquisition_span.to_index(rk.periodicity.Type.YEAR),
            data=[-abs(params['acquisition_price'])],
            units=params['units'],
            name='Acquisition Price')

        self.investment_cashflows = rk.flux.Stream(
            name='Investment Cashflows',
            flows=[self.ncf.sum(), self.disposition, self.acquisition],
            period_type=params['period_type'])

        self.investment_cashflows.frame = self.investment_cashflows.frame[:-1]

        # IRR is displayed in the right hand panel...
        self.irr = self.investment_cashflows.sum().xirr()
