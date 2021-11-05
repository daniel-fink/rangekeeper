import pandas as pd
import scipy as sp
import numpy as np
from numba import jit
import typing

import distribution, flux, phase, periodicity, units

period_type = periodicity.Periodicity.Type.year
phase = phase.Phase.from_num_periods(name="Phase",
                                     start_date=pd.Timestamp(2020, 1, 1),
                                     period_type=period_type,
                                     num_periods=26)

# Initial Price Factor:
#
# This will govern the central tendency or deterministic component of the initial rent value.
initial_price_factor = 1.

# Rent Yield:
#
# This governs the base rental (net income) value as a fraction of asset value.
# To normalize the values by giving them a "base" value of 1.00,
# we have set this equal to the cap rate (net income yield) times the initial price factor above.
# This will give a base asset value of 1.00 if the initial price factor is 1.00.
rent_yield = 0.05
rent_error = 0.005

cap_rate = 0.05

current_rent = initial_price_factor * cap_rate

# Initial Rent Value Distribution:
#
# This is a X distribution.
# Note that the random outcome is generated only once per history, here in the first year.
# There is only one "initial" rent level in a given history.
# The uncertainty is revealed in Year 1. Year 0 is fixed because it is observable already in the present.
initial_rent_dist = distribution.PERT(peak=current_rent,
                                      weighting=4.,
                                      minimum=current_rent - rent_error,
                                      maximum=current_rent + rent_error)
initial_rent = initial_rent_dist.sample()
initial_rent = .04888252496410490

# Growth Trend Relative to Proforma:
#
# Normally this should be zero.
# But to adjust for convexity effects on average cash flow levels for comparison across different price dynamics inputs assumptions,
# you may need to adjust this trend.
# For example, a symmetric cap rate cycle will impart a positive bias into the simulated future cash flows relative to the proforma,
# while Black Swans and cycle phase or other inputs may impart a negative bias.
# Enter a relative trend rate here to counteract such bias (under the assumption that the proforma is unbiased).
# Check the t-stat in column K to see if the resulting comparison of NPV (without flexibility) relative to the proforma is statistically insignificant.
# If you're not comparing across different price dynamics, then you can just leave this input at zero.
# That is, if you're just comparing flexible vs inflexible, any bias will cancel out.

# This will govern the central tendency of the long-run growth rate trend that will apply over the entire scenario.
# As Pricing Factors are only RELATIVE TO the Base Case pro-forma which should contain any realistic expected growth,
# the default value input here should normally be zero.
# However, you should check to see if there is a convexity bias that needs to be corrected with this trend input.
trend_delta = 0.
trend_error = 0.005

# Uncertainty Distribution
#
# This is the realization of uncertainty in the long-run trend growth rate.
# Here we model this uncertainty with a X distribution.
# Note that the random outcome is generated only once per history.
# There is only one "long-term trend rate" in the rent growth in any given history.
# In a Monte Carlo simulation (such as you can do using a Data Table),
# a new random number would be automatically generated here for each of the (thousands of) "trials" you run.
# This is so for all of the random number generators in this workbook.
trend_dist = distribution.PERT(peak=trend_delta,
                               weighting=4.,
                               minimum=trend_delta - trend_error,
                               maximum=trend_delta + trend_error)
trend_rate = trend_dist.sample()
trend_rate = 0.0008597333364944
# Trend:
#
# Note that the trend is geometric.
# This makes sense if this rent series will translate via a cap rate to a property asset value series,
# as asset values cannot be negative.
trend = flux.Flow.from_initial(name='Trend',
                               initial=initial_rent,
                               index=phase.to_index(period_type),
                               dist=distribution.Exponential(rate=trend_rate,
                                                             num_periods=phase.duration(period_type=period_type,
                                                                                        inclusive=True)),
                               units=units.Units.Type.scalar)

# Volatility
#
# "Volatility" refers to the standard deviation across time (longitudinal dispersion),
# in the changes or returns (differences from one period to the next).
# Volatility "accumulates" in the sense that the realization of the change in one period
# becomes embedded in the level (of rents) going forward into the next period,
# whose change is then added on top of the previous level (of rents).
# The volatility realizations tracked in this column apply only to the "innovations" in the rent level.
# If there is autoregression (next columns) then that will also affect
# the annual volatility in the rent changes.
#
# "Innovations" refers to the component of changes or returns that is completely "new" each period,
# the component that could not have been predicted at all.

# This is a normal (Gaussian) distribution.
# Note that volatility is realized (new random increment is generated) in EACH period,
# so that this "risk" outcome accumulates in the history of rent levels.
# But this is just the volatility in the innovations; if there is autoregression then that will also affect the annual volatility.
# Cycles will also affect the average volatility observed empirically across the scenario.
volatility_per_period = .08
volatilities = pd.Series(data=[sp.special.ndtri(distribution.Uniform().sample()) * volatility_per_period
                               # the ndtri() function replicates excel's NORMSINV(). See https://stackoverflow.com/questions/20626994/how-to-calculate-the-inverse-of-the-normal-cumulative-distribution-function-in-p/20627638
                               for x in range(phase.duration(period_type=period_type,
                                                             inclusive=True)
                                              )],
                         index=phase.to_index(period_type))
volatility = flux.Flow(movements=volatilities,
                       units=units.Units.Type.scalar,
                       name='Volatility')


# Autoregressive Returns
#
# This reflects the inertia in the price movements.
# This value indicates the degree of inertia for the relevant market.
# This is the autoregression parameter,
# which indicates what proportion of the previous period's return (price change)
# will automatically become a component of the current period's return (price change).
# In most real estate markets this would typically be a positive fraction,
# perhaps in the range +0.1 to +0.5.
# In more liquid and informationally efficient asset markets such as stock markets
# you might leave this at zero (no inertia).
# A "noisy" market would have a negative autoregression parameter,
# however, we deal with noise separately.

@jit(nopython=True)
def calculate_autoregression(autoregression: float,
                             volatility: [float]):
    ar_returns = []
    for i in range(len(volatility)):
        if i == 0:
            ar_returns.append(volatility[0])
        else:
            ar_returns.append(volatility[i] + (autoregression * ar_returns[i - 1]))
    return ar_returns


autoregression = .2
autoregressive_returns = flux.Flow(movements=pd.Series(data=calculate_autoregression(autoregression=autoregression,
                                                                                     volatility=volatility.movements.to_list()),
                                                       index=volatility.movements.index),
                                   units=units.Units.Type.scalar,
                                   name='Autoregressive Returns')


# Mean Reversion
# This parameter determines the strength (or speed) of the mean reversion tendency in the price levels.
# It is the proportion of the previous period's difference of the price level
# from the long-term trend price level that will be eliminated in the current price level.
# This parameter should be between zero and 1, probably not very close to 1.
# For example, if the previous price level were 1.0, and the long-term trend price level for that period were 1.2,
# and if the mean reversion parameter were 0.5,
# then 0.5*(1.2-1.0) = 0.10 will be added to this period's price level.

@jit(nopython=True)
def calculate_mean_reversion(mean_reversion_param: float,
                             trend: [float]):
    mr_returns = []
    for i in range(len(trend)):
        if i == 0:
            mr_returns.append(trend[0])
        else:
            mr_returns.append(mean_reversion_param * (trend[i] - mr_returns[i - 1]))
    return mr_returns


mean_reversion_param = .3
mean_reversion_returns = flux.Flow(
    movements=pd.Series(data=calculate_mean_reversion(mean_reversion_param=mean_reversion_param,
                                                      trend=trend.movements.to_list()),
                        index=trend.movements.index),
    units=units.Units.Type.scalar,
    name='Mean Reversion Returns')


# Cumulative Volatility:
# Accumulate the volatility generated in the previous column, also reflecting the mean reversion tendency.

@jit(nopython=True)
def calculate_volatility_accumulation(trend_rate: float,
                                      trend: [float],
                                      ar_returns: [float],
                                      mr_returns: [float]):
    accumulated_volatility = []
    for i in range(len(trend)):
        if i == 0:
            accumulated_volatility.append(trend[0])
        else:
            accumulated_volatility.append(accumulated_volatility[i - 1] * (1 + trend_rate + ar_returns[i]) + mr_returns[i])
    return accumulated_volatility


cumulative_volatility = flux.Flow(movements=pd.Series(data=calculate_volatility_accumulation(trend_rate=trend_rate,
                                                                                             trend=trend.movements.to_list(),
                                                                                             ar_returns=autoregressive_returns.movements.to_list(),
                                                                                             mr_returns=mean_reversion_returns.movements.to_list()),
                                                      index=trend.movements.index),
                                  units=units.Units.Type.scalar,
                                  name='Cumulative')

volatility_frame = flux.Aggregation(name="Volatility",
                                    aggregands=[trend, volatility, autoregressive_returns, mean_reversion_returns, cumulative_volatility],
                                    periodicity_type=period_type)
