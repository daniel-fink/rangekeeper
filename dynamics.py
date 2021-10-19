import pandas as pd
import numpy as np

import distribution, flux, phase, periodicity, units

phase = phase.Phase.from_num_periods(name="Phase",
                                     start_date=pd.Timestamp(2020, 1, 1),
                                     period_type=periodicity.Periodicity.Type.year,
                                     num_periods=24)

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
initial_rent = .051633489630302

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
                               minimum=trend_delta-trend_error,
                               maximum=trend_delta + trend_error)
trend = trend_dist.sample()
trend = -0.0041725610227779
# Trend:
#
# Note that the trend is geometric.
# This makes sense if this rent series will translate via a cap rate to a property asset value series,
# as asset values cannot be negative.
trend = flux.Flow.from_initial(name='Trend',
                               initial=initial_rent,
                               index=phase.to_index(periodicity.Periodicity.Type.year),
                               dist=distribution.Exponential(rate=trend,
                                                             num_periods=phase.duration(period_type=periodicity.Periodicity.Type.year,
                                                                                        inclusive=True)),
                               units=units.Units.Type.scalar)




