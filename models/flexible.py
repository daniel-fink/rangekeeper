import pandas as pd

try:
    import escalation
    import distribution
    import periodicity
    from flux import Flow, Aggregation
    from phase import Phase
except:
    import modules.rangekeeper.distribution
    from modules.rangekeeper.flux import Flow, Aggregation
    from modules.rangekeeper.periodicity import periodicity
    from modules.rangekeeper.phase import Phase


# Base Model:
class Model:
    def __init__(self, params: dict):
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

        self.disposition_phase = Phase.from_num_periods(
            name='Disposition',
            start_date=periodicity.date_offset(
                date=self.acquisition_phase.start_date,
                period_type=periodicity.Type.year,
                num_periods=params['num_periods']),
            period_type=periodicity.Type.year,
            num_periods=1)

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
        self.escalation = escalation.Exponential(
            rate=params['growth_rate'],
            num_periods=self.noi_calc_phase.duration(
                period_type=params['period_type'],
                inclusive=True))

        # Potential Gross Income
        self.pgi = Flow.from_extrapolated_initial(
            name='Potential Gross Income',
            initial=params['initial_pgi'],
            index=self.noi_calc_phase.to_index(period_type=params['period_type']),
            extrapolation=self.escalation,
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

        # Reversion:
        # We no longer need the noi_calc_phase:
        operation_periods = self.operation_phase.to_index(period_type=params['period_type'])
        self.cap_rates = params['asset_market_dist'].sample(size=operation_periods.size)
        self.sale_values = Flow.from_periods(
            name='Sale Values',
            # We no longer need the noi_calc_phase:
            index=operation_periods,
            data=list(self.ncf.sum().movements[
                      :self.operation_phase.end_date] / self.cap_rates),
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

        self.disposition = Flow(
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

        self.pv_ncf_agg = Aggregation(
            name='Discounted Net Cashflow Sums',
            aggregands=[self.pv_ncf, self.pv_disposition],
            period_type=params['period_type'])

        self.pv_sums = self.pv_ncf_agg.sum()

        self.pv_sums.movements = self.pv_sums.movements[:self.disposition_date]

        self.acquisition = Flow.from_periods(
            index=self.acquisition_phase.to_index(periodicity.Type.year),
            data=[-abs(params['acquisition_price'])],
            units=params['units'],
            name='Acquisition Price')

        self.investment_cashflows = Aggregation(
            name='Investment Cashflows',
            aggregands=[self.ncf.sum(), self.disposition, self.acquisition],
            period_type=params['period_type'])

        self.investment_cashflows.aggregation = self.investment_cashflows.aggregation[:self.disposition_date]
        self.irr = self.investment_cashflows.sum().xirr()
        self.npv = self.investment_cashflows.sum().xnpv(params['discount_rate'])
