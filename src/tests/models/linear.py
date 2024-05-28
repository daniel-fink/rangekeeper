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
            duration=rk.duration.Type.YEAR,
            amount=1)

        self.operation_span = rk.span.Span.from_duration(
            name='Operation',
            date=rk.duration.offset(
                date=self.acquisition_span.end_date,
                duration=rk.duration.Type.DAY,
                amount=1),
            duration=rk.duration.Type.YEAR,
            amount=params['num_periods'])

        self.disposition_span = rk.span.Span.from_duration(
            name='Disposition',
            date=rk.duration.offset(
                date=self.acquisition_span.start_date,
                duration=rk.duration.Type.YEAR,
                amount=params['num_periods']),
            duration=rk.duration.Type.YEAR,
            amount=1)

        self.projection_span = rk.span.Span.from_duration(
            name='Projection',
            date=rk.duration.offset(
                date=self.operation_span.end_date,
                duration=rk.duration.Type.DAY,
                amount=1),
            duration=rk.duration.Type.YEAR,
            amount=1)

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
                sequence=self.noi_calc_span.to_sequence(frequency=params['frequency'])),
            units=params['units'])


        # Vacancy Allowance
        # This should be displayed as a row in a table with xxxx, xxx,....
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

        # Disposition (Reversion):
        sale_value = self.ncf.sum().movements.tail(1).item() / params['cap_rate']
        self.disposition = rk.flux.Flow.from_sequence(
            name='Disposition',
            sequence=self.disposition_span.to_sequence(frequency=params['frequency']),
            data=[sale_value],
            units=params['units'])

        # Net Cash Flows with Disposition:
        self.ncf_disposition = self.ncf.duplicate().trim_to_span(span=self.operation_span)
        self.ncf_disposition.append(flows=[self.disposition])

        # Calculate the Present Value of the NCFs:
        self.pv_ncf = self.ncf.sum().pv(
            frequency=params['frequency'],
            rate=params['discount_rate'])

        # Calculate the Present Value of Disposition CFs:
        self.pv_disposition = self.disposition.pv(
            frequency=params['frequency'],
            rate=params['discount_rate'])

        self.pv_ncf_agg = rk.flux.Stream(
            name='Discounted Net Cashflows',
            flows=[self.pv_ncf, self.pv_disposition],
            frequency=params['frequency'])

        self.pv_sums = self.pv_ncf_agg.sum()
        self.pv_sums.movements = self.pv_sums.movements[:-1]

        self.acquisition = rk.flux.Flow.from_sequence(
            sequence=self.acquisition_span.to_sequence(frequency=rk.duration.Type.YEAR),
            data=[-abs(params['acquisition_price'])],
            units=params['units'],
            name='Acquisition Price')

        self.investment_cashflows = rk.flux.Stream(
            name='Investment Cashflows',
            flows=[self.ncf.sum(), self.disposition, self.acquisition],
            frequency=params['frequency'])

        self.investment_cashflows.frame = self.investment_cashflows.frame[:-1]

        # IRR is displayed in the right hand panel...
        self.irr = self.investment_cashflows.sum().xirr()
