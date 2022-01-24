import distribution
from flux import Flow, Aggregation
from periodicity import Periodicity
from phase import Phase


# Base Model:
class Model:
    def __init__(self,
                 params: dict):
        # Phasing:
        self.acquisition_phase = Phase.from_num_periods(
            name='Acquisition',
            start_date=params['start_date'],
            period_type=Periodicity.Type.year,
            num_periods=1)

        self.operation_phase = Phase.from_num_periods(
            name='Operation',
            start_date=Periodicity.date_offset(
                date=self.acquisition_phase.end_date,
                period_type=Periodicity.Type.day,
                num_periods=1),
            period_type=Periodicity.Type.year,
            num_periods=params['num_periods'])

        self.reversion_phase = Phase.from_num_periods(
            name='Disposition',
            start_date=Periodicity.date_offset(
                date=self.acquisition_phase.start_date,
                period_type=Periodicity.Type.year,
                num_periods=params['num_periods']),
            period_type=Periodicity.Type.year,
            num_periods=1)

        self.projection_phase = Phase.from_num_periods(
            name='Projection',
            start_date=Periodicity.date_offset(
                date=self.operation_phase.end_date,
                period_type=Periodicity.Type.day,
                num_periods=1),
            period_type=Periodicity.Type.year,
            num_periods=1)

        self.noi_calc_phase = Phase.merge(
            name='NOI Calculation Phase',
            phases=[self.operation_phase, self.projection_phase])

        # Factors:
        self.distribution = distribution.Exponential(
            rate=params['growth_rate'],
            num_periods=self.noi_calc_phase.duration(
                period_type=params['period_type'],
                inclusive=True))

        # Cashflows:
        # Potential Gross Income
        self.pgi = Flow.from_initial(
            name='Potential Gross Income',
            initial=params['initial_pgi'],
            index=self.noi_calc_phase.to_index(periodicity=params['period_type']),
            dist=self.distribution,
            units=params['units'])

        # Vacancy Allowance
        # This should be displayed as a row in a table with xxxx, xxx,....
        self.vacancy = Flow.from_periods(
            name='Vacancy Allowance',
            periods=self.noi_calc_phase.to_index(periodicity=params['period_type']),
            data=self.pgi.movements * params['vacancy_rate'],
            units=params['units']).invert()

        # Effective Gross Income:
        self.egi = Aggregation(
            name='Effective Gross Income',
            aggregands=[self.pgi, self.vacancy],
            periodicity=params['period_type'])

        # Operating Expenses:
        self.opex = Flow.from_periods(
            name='Operating Expenses',
            periods=self.noi_calc_phase.to_index(periodicity=params['period_type']),
            data=self.pgi.movements * params['opex_pgi_ratio'],
            units=params['units']).invert()

        # Net Operating Income:
        self.noi = Aggregation(
            name='Net Operating Income',
            aggregands=[self.egi.sum('Effective Gross Income'), self.opex],
            periodicity=params['period_type'])

        # Capital Expenses:
        self.capex = Flow.from_periods(
            name='Capital Expenditures',
            periods=self.noi_calc_phase.to_index(periodicity=params['period_type']),
            data=self.pgi.movements * params['capex_pgi_ratio'],
            units=params['units']).invert()

        # Net Cashflows:
        self.ncf = Aggregation(
            name='Net Cashflows',
            aggregands=[self.noi.sum(), self.capex],
            periodicity=params['period_type'])

        # Reversion:
        sale_value = self.ncf.sum().movements.tail(1).item() / params['cap_rate']
        self.reversion = Flow.from_periods(
            name='Reversion',
            periods=self.reversion_phase.to_index(periodicity=params['period_type']),
            data=[sale_value],
            units=params['units'])

        # Net Cash Flows with Reversion:
        self.ncf_reversion = self.ncf.duplicate().trim_to_phase(self.operation_phase)
        self.ncf_reversion.append(aggregands=[self.reversion])
        # self.ncf_reversion = self.ncf_reversion.sum()

        #self.npv = self.ncf_reversion.sum().xnpv(params['discount_rate'])

        # Calculate the Present Value of the NCFs:
        self.pv_ncf = self.ncf.sum().pv(
            periodicity=params['period_type'],
            discount_rate=params['discount_rate'])

        # Calculate the Present Value of Reversion CFs:
        self.pv_reversion = self.reversion.pv(
            periodicity=params['period_type'],
            discount_rate=params['discount_rate'])

        # Add Cumulative Sum of Discounted Net Cashflows to each period's Discounted Reversion:
        # pv_ncf_cumsum = Flow(movements=self.pv_ncf.movements.cumsum(),
        #                      name='Discounted Net Cashflow Cumulative Sums',
        #                      units=params['units'])
        self.pv_ncf_agg = Aggregation(
            name='Discounted Net Cashflows',
            aggregands=[self.pv_ncf, self.pv_reversion],
            periodicity=params['period_type'])

        self.pv_sums = self.pv_ncf_agg.sum()
        self.pv_sums.movements = self.pv_sums.movements[:-1]

        self.acquisition = Flow.from_periods(
            periods=self.acquisition_phase.to_index(Periodicity.Type.year),
            data=[-abs(params['acquisition_price'])],
            units=params['units'],
            name='Acquisition Price')

        self.investment_cashflows = Aggregation(
            name='Investment Cashflows',
            aggregands=[self.ncf.sum(), self.reversion, self.acquisition],
            periodicity=params['period_type'])

        self.investment_cashflows.aggregation = self.investment_cashflows.aggregation[:-1]

        # IRR is displayed in the right hand panel...
        self.irr = self.investment_cashflows.sum().xirr()
