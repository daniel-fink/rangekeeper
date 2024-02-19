# from __future__ import annotations
# from typing import List
#
#
# try:
#     import escalation
#     from flux import Flow, Stream
#     from periodicity import Periodicity
#     from span import Span
# except:
#     import modules.rangekeeper.distribution
#     from modules.rangekeeper.flux import Flow, Stream
#     from modules.rangekeeper.periodicity import Periodicity
#     from modules.rangekeeper.span import Span
#
#
# class Graph:
#     def __init__(
#             self,
#             params: dict):
#         if 'podium' in params:
#
#
#
#
#
# # Base Model:
# class Model:
#     def __init__(
#             self,
#             params: dict):
#
#         # Phasing:
#         self.acquisition_span = Span.from_num_periods(
#             name='Acquisition',
#             start_date=params['start_date'],
#             period_type=Periodicity.Type.year,
#             num_periods=1)
#
#         self.operation_span = Span.from_num_periods(
#             name='Operation',
#             start_date=Periodicity.offset_date(
#                 date=self.acquisition_span.end_date,
#                 period_type=Periodicity.Type.day,
#                 num_periods=1),
#             period_type=Periodicity.Type.year,
#             num_periods=params['num_periods'])
#
#         self.disposition_span = Span.from_num_periods(
#             name='Disposition',
#             start_date=Periodicity.offset_date(
#                 date=self.acquisition_span.start_date,
#                 period_type=Periodicity.Type.year,
#                 num_periods=params['num_periods']),
#             period_type=Periodicity.Type.year,
#             num_periods=1)
#
#         self.projection_span = Span.from_num_periods(
#             name='Projection',
#             start_date=Periodicity.offset_date(
#                 date=self.operation_span.end_date,
#                 period_type=Periodicity.Type.day,
#                 num_periods=1),
#             period_type=Periodicity.Type.year,
#             num_periods=1)
#
#         self.noi_calc_span = Span.merge(
#             name='NOI Calculation Span',
#             spans=[self.operation_span, self.projection_span])
#
#         # Factors:
#         self.distribution = distribution.Exponential(
#             rate=params['growth_rate'],
#             num_periods=self.noi_calc_span.duration(
#                 period_type=params['period_type'],
#                 inclusive=True))
#
#         # Cashflows:
#         # Potential Gross Income
#         self.pgi = Flow.from_initial(
#             name='Potential Gross Income',
#             initial=params['initial_pgi'],
#             index=self.noi_calc_span.to_index(periodicity=params['period_type']),
#             dist=self.distribution,
#             units=params['units'])
#
#         # Vacancy Allowance
#         # This should be displayed as a row in a table with xxxx, xxx,....
#         self.vacancy = Flow.from_periods(
#             name='Vacancy Allowance',
#             periods=self.noi_calc_span.to_index(periodicity=params['period_type']),
#             data=self.pgi.movements * params['vacancy_rate'],
#             units=params['units']).invert()
#
#         # Effective Gross Income:
#         self.egi = Stream(
#             name='Effective Gross Income',
#             flows=[self.pgi, self.vacancy],
#             periodicity=params['period_type'])
#
#         # Operating Expenses:
#         self.opex = Flow.from_periods(
#             name='Operating Expenses',
#             periods=self.noi_calc_span.to_index(periodicity=params['period_type']),
#             data=self.pgi.movements * params['opex_pgi_ratio'],
#             units=params['units']).invert()
#
#         # Net Operating Income:
#         self.noi = Stream(
#             name='Net Operating Income',
#             flows=[self.egi.sum('Effective Gross Income'), self.opex],
#             periodicity=params['period_type'])
#
#         # Capital Expenses:
#         self.capex = Flow.from_periods(
#             name='Capital Expenditures',
#             periods=self.noi_calc_span.to_index(periodicity=params['period_type']),
#             data=self.pgi.movements * params['capex_pgi_ratio'],
#             units=params['units']).invert()
#
#         # Net Cashflows:
#         self.ncf = Stream(
#             name='Net Cashflows',
#             flows=[self.noi.sum(), self.capex],
#             periodicity=params['period_type'])
#
#         # Disposition (Reversion):
#         sale_value = self.ncf.sum().movements.tail(1).item() / params['cap_rate']
#         self.disposition = Flow.from_periods(
#             name='Disposition',
#             periods=self.disposition_span.to_index(periodicity=params['period_type']),
#             data=[sale_value],
#             units=params['units'])
#
#         # Net Cash Flows with Disposition:
#         self.ncf_disposition = self.ncf.duplicate().trim_to_span(self.operation_span)
#         self.ncf_disposition.append(flows=[self.disposition])
#
#         # Calculate the Present Value of the NCFs:
#         self.pv_ncf = self.ncf.sum().pv(
#             periodicity=params['period_type'],
#             discount_rate=params['discount_rate'])
#
#         # Calculate the Present Value of Disposition CFs:
#         self.pv_disposition = self.disposition.pv(
#             periodicity=params['period_type'],
#             discount_rate=params['discount_rate'])
#
#         self.pv_ncf_agg = Stream(
#             name='Discounted Net Cashflows',
#             flows=[self.pv_ncf, self.pv_disposition],
#             periodicity=params['period_type'])
#
#         self.pv_sums = self.pv_ncf_agg.sum()
#         self.pv_sums.movements = self.pv_sums.movements[:-1]
#
#         self.acquisition = Flow.from_periods(
#             periods=self.acquisition_span.to_index(Periodicity.Type.year),
#             data=[-abs(params['acquisition_price'])],
#             units=params['units'],
#             name='Acquisition Price')
#
#         self.investment_cashflows = Stream(
#             name='Investment Cashflows',
#             flows=[self.ncf.sum(), self.disposition, self.acquisition],
#             periodicity=params['period_type'])
#
#         self.investment_cashflows.frame = self.investment_cashflows.frame[:-1]
#
#         # IRR is displayed in the right hand panel...
#         self.irr = self.investment_cashflows.sum().xirr()
