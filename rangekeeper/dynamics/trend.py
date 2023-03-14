# import distribution, span, periodicity, projection, flux
#
#
# class Trend:
#     def __init__(
#             self,
#             span: span.Span,
#             period_type: periodicity.Type,
#             params: dict):
#         self.rent_mean = params['rent_mean']
#         """
#         Initial Rent Value Distribution:
#         This is a Normal distribution.
#         Note that the random outcome is generated only once per history, here in the first year.
#         There is only one "initial" rent level in a given history.
#         The uncertainty is revealed in Year 1. Year 0 is fixed because it is observable already in the present.
#         """
#
#         initial_rent_dist = distribution.PERT(
#             peak=self.rent_mean,
#             weighting=4.,
#             minimum=self.rent_mean - params['rent_residual'],
#             maximum=self.rent_mean + params['rent_residual'])
#         self.initial_rent = initial_rent_dist.sample()
#         # self.initial_rent = 0.0511437
#
#         """
#         Uncertainty Distribution
#         This is the realization of uncertainty in the long-run trend growth rate.
#         Here we model this uncertainty with a Normal (PERT) distribution.
#         Note that the random outcome is generated only once per history.
#         There is only one "long-term trend rate" in the rent growth in any given history.
#         In a Monte Carlo simulation (such as you can do using a Data Table),
#         a new random number would be automatically generated here for each of the (thousands of) "trials" you run.
#         This is so for all of the random number generators in this workbook.
#         """
#
#         trend_dist = distribution.PERT(
#             peak=params['trend_mean'],
#             weighting=4.,
#             minimum=params['trend_mean'] - params['trend_residual'],
#             maximum=params['trend_mean'] + params['trend_residual'])
#         self.trend_rate = trend_dist.sample()
#         # self.trend_rate = 0.00698263624
#
#         trend_proj = projection.Extrapolation(
#             form=projection.extrapolation.Compounding(rate=self.trend_rate),
#             sequence=span.to_index(period_type=period_type))
#
#         self.trend = flux.Flow.from_projection(
#             name='Market Trend',
#             value=self.initial_rent,
#             proj=trend_proj)
#         """
#         Trend:
#         Note that the trend is geometric.
#         This makes sense if this rent series will translate via a cap rate to a property asset value series,
#         as asset values cannot be negative.
#         """
