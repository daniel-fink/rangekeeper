import rangekeeper as rk


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

        self.disposition_phase = rk.phase.Phase.from_num_periods(
            name='Disposition',
            date=rk.periodicity.date_offset(
                date=self.acquisition_phase.start_date,
                period_type=rk.periodicity.Type.year,
                num_periods=params['num_periods']),
            period_type=rk.periodicity.Type.year,
            num_periods=1)

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

        # Factors:
        self.escalation = rk.projection.Extrapolation.Compounding(rate=params['growth_rate'])

        # Cashflows:
        # Potential Gross Income
        self.pgi = rk.flux.Flow.from_projection(
            name='Potential Gross Income',
            value=params['initial_pgi'],
            proj=rk.projection.Extrapolation(
                form=self.escalation,
                sequence=self.noi_calc_phase.to_index(period_type=params['period_type'])),
            units=params['units'])

        # Vacancy Allowance
        # This should be displayed as a row in a table with xxxx, xxx,....
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

        # Disposition (Reversion):
        sale_value = self.ncf.sum().movements.tail(1).item() / params['cap_rate']
        self.disposition = rk.flux.Flow.from_periods(
            name='Disposition',
            index=self.disposition_phase.to_index(period_type=params['period_type']),
            data=[sale_value],
            units=params['units'])

        # Net Cash Flows with Disposition:
        self.ncf_disposition = self.ncf.duplicate().trim_to_phase(self.operation_phase)
        self.ncf_disposition.append(affluents=[self.disposition])

        # Calculate the Present Value of the NCFs:
        self.pv_ncf = self.ncf.sum().pv(
            period_type=params['period_type'],
            discount_rate=params['discount_rate'])

        # Calculate the Present Value of Disposition CFs:
        self.pv_disposition = self.disposition.pv(
            period_type=params['period_type'],
            discount_rate=params['discount_rate'])

        self.pv_ncf_agg = rk.flux.Confluence(
            name='Discounted Net Cashflows',
            affluents=[self.pv_ncf, self.pv_disposition],
            period_type=params['period_type'])

        self.pv_sums = self.pv_ncf_agg.sum()
        self.pv_sums.movements = self.pv_sums.movements[:-1]

        self.acquisition = rk.flux.Flow.from_periods(
            index=self.acquisition_phase.to_index(rk.periodicity.Type.year),
            data=[-abs(params['acquisition_price'])],
            units=params['units'],
            name='Acquisition Price')

        self.investment_cashflows = rk.flux.Confluence(
            name='Investment Cashflows',
            affluents=[self.ncf.sum(), self.disposition, self.acquisition],
            period_type=params['period_type'])

        self.investment_cashflows.frame = self.investment_cashflows.frame[:-1]

        # IRR is displayed in the right hand panel...
        self.irr = self.investment_cashflows.sum().xirr()
