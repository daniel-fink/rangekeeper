import pandas as pd

try:
    import projection
    import distribution
    import periodicity
    from flux import Flow, Confluence
    from phase import Phase
except:
    import modules.rangekeeper.distribution
    from modules.rangekeeper.flux import Flow, Confluence
    from modules.rangekeeper.periodicity import periodicity
    from modules.rangekeeper.phase import Phase


# Base Model:
class Model:
    def __init__(
            self,
            params: dict):

        # Phasing:
        self.acquisition_phase = Phase.from_num_periods(
            name='Acquisition',
            date=params['start_date'],
            period_type=periodicity.Type.year,
            num_periods=1)

        self.operation_phase = Phase.from_num_periods(
            name='Operation',
            date=periodicity.date_offset(
                date=self.acquisition_phase.end_date,
                period_type=periodicity.Type.day,
                num_periods=1),
            period_type=periodicity.Type.year,
            num_periods=params['num_periods'])

        self.disposition_phase = Phase.from_num_periods(
            name='Reversion',
            date=periodicity.date_offset(
                date=self.acquisition_phase.start_date,
                period_type=periodicity.Type.year,
                num_periods=params['num_periods']),
            period_type=periodicity.Type.year,
            num_periods=1)

        self.projection_phase = Phase.from_num_periods(
            name='Projection',
            date=periodicity.date_offset(
                date=self.operation_phase.end_date,
                period_type=periodicity.Type.day,
                num_periods=1),
            period_type=periodicity.Type.year,
            num_periods=1)

        self.noi_calc_phase = Phase.merge(
            name='NOI Calculation Phase',
            phases=[self.operation_phase, self.projection_phase])

        # Cashflows:
        self.escalation = projection.ExponentialExtrapolation(rate=params['growth_rate'])

        # Potential Gross Income
        self.pgi = Flow.from_projection(
            name='Potential Gross Income',
            value=params['initial_pgi'],
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            proj=self.escalation,
            units=params['units'])

        factors = params['space_market_dist'].sample(size=self.pgi.movements.size)

        self.pgi_factor = Flow(
            movements=pd.Series(
                data=factors,
                index=self.pgi.movements.index,
                dtype=float),
            units=params['units'],
            name='Space Market Pricing Factors')

        self.pgi = Flow(
            movements=self.pgi.movements * self.pgi_factor.movements,
            units=params['units'],
            name=self.pgi.name)

        # Vacancy Allowance
        self.vacancy = Flow.from_periods(
            name='Vacancy Allowance',
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['vacancy_rate'],
            units=params['units']).invert()

        # Effective Gross Income:
        self.egi = Confluence(
            name='Effective Gross Income',
            affluents=[self.pgi, self.vacancy],
            period_type=params['period_type'])

        # Operating Expenses:
        self.opex = Flow.from_periods(
            name='Operating Expenses',
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['opex_pgi_ratio'],
            units=params['units']).invert()

        # Net Operating Income:
        self.noi = Confluence(
            name='Net Operating Income',
            affluents=[self.egi.sum('Effective Gross Income'), self.opex],
            period_type=params['period_type'])

        # Capital Expenses:
        self.capex = Flow.from_periods(
            name='Capital Expenditures',
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            data=self.pgi.movements * params['capex_pgi_ratio'],
            units=params['units']).invert()

        # Net Cashflows:
        self.ncf = Confluence(
            name='Net Cashflows',
            affluents=[self.noi.sum(), self.capex],
            period_type=params['period_type'])

        # Disposition:
        sale_value = self.ncf.sum().movements.tail(1).item() / params['cap_rate']
        self.disposition = Flow.from_periods(
            name='Disposition',
            index=self.disposition_phase.to_index(period_type=params['period_type']),
            data=[sale_value],
            units=params['units'])

        # Calculate the Present Value of the NCFs:
        self.pv_ncf = self.ncf.sum().pv(
            period_type=params['period_type'],
            discount_rate=params['discount_rate'])

        # Calculate the Present Value of Reversion CFs:
        self.pv_disposition = self.disposition.pv(
            period_type=params['period_type'],
            discount_rate=params['discount_rate'])

        # Add Cumulative Sum of Discounted Net Cashflows to each period's Discounted Disposition:
        # pv_ncf_cumsum = Flow(movements=self.pv_ncf.movements.cumsum(),
        #                      name='Discounted Net Cashflow Cumulative Sums',
        #                      units=params['units'])
        self.pv_ncf_agg = Confluence(
            name='Discounted Net Cashflows',
            affluents=[self.pv_ncf, self.pv_disposition],
            period_type=params['period_type'])

        self.pv_sums = self.pv_ncf_agg.sum()
        self.pv_sums.movements = self.pv_sums.movements[:-1]

        self.acquisition = Flow.from_periods(
            index=self.acquisition_phase.to_index(periodicity.Type.year),
            data=[-abs(params['acquisition_price'])],
            units=params['units'],
            name='Acquisition Price')

        self.investment_cashflows = Confluence(
            name='Investment Cashflows',
            affluents=[self.ncf.sum(), self.disposition, self.acquisition],
            period_type=params['period_type'])

        self.investment_cashflows.frame = self.investment_cashflows.frame[:-1]
        self.irr = self.investment_cashflows.sum().xirr()
