# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.

# In addition, in order to enable pytest to find all modules,
# run tests via a 'python -m pytest tests/<test_file>.py' command from the root directory of this project

import math
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

import dynamics, periodicity, phase, distribution

matplotlib.use('TkAgg')
plt.style.use('seaborn')  # pretty matplotlib plots
plt.rcParams['figure.figsize'] = (12, 8)


class TestDynamics:
    period_type = periodicity.Periodicity.Type.year
    phase = phase.Phase.from_num_periods(name="Phase",
                                         start_date=pd.Timestamp(2021, 1, 1),
                                         period_type=period_type,
                                         num_periods=25)

    def test_dynamics(self):
        rental_market_params = {
            # Rent Yield:
            # This governs the base rental (net income) value as a fraction of asset value.
            # To normalize the values by giving them a "base" value of 1.00,
            # we have set this equal to the cap rate (net income yield) times the initial price factor above.
            # This will give a base asset value of 1.00 if the initial price factor is 1.00.
            #
            # Initial Price Factor:
            # This will govern the central tendency or deterministic component of the initial rent value.
            'initial_price_factor': 1.,
            'cap_rate': .05,
            'rent_error': .005,

            # Growth Trend Relative to Proforma:
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
            'trend_delta': 0.,
            'trend_error': .005,

            # Volatility:
            # "Volatility" refers to the standard deviation across time (longitudinal dispersion),
            # in the changes or returns (differences from one period to the next).
            # Volatility "accumulates" in the sense that the realization of the change in one period
            # becomes embedded in the level (of rents) going forward into the next period,
            # whose change is then added on top of the previous level (of rents).
            # The volatility realizations tracked in this column apply only to the "innovations" in the rent level.
            # If there is autoregression (next columns) then that will also affect
            # the annual volatility in the rent changes.
            'volatility_per_period': .08,

            # Autoregressive Returns:
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
            'autoregression_param': .2,

            # Mean Reversion
            # This parameter determines the strength (or speed) of the mean reversion tendency in the price levels.
            # It is the proportion of the previous period's difference of the price level
            # from the long-term trend price level that will be eliminated in the current price level.
            # This parameter should be between zero and 1, probably not very close to 1.
            # For example, if the previous price level were 1.0, and the long-term trend price level for that period were 1.2,
            # and if the mean reversion parameter were 0.5,
            # then 0.5*(1.2-1.0) = 0.10 will be added to this period's price level.
            'mean_reversion_param': .3,
            }

        rental_market_dynamics = dynamics.RentalMarketDynamics(rental_market_params)

        # dynamics.trend.display()
        # # dynamics.volatility.display()
        # # dynamics.autoregressive_returns.display()
        #
        # # print(type(dynamics.volatility.movements.index))
        #
        # dynamics.volatility.display()
        # dynamics.autoregressive_returns.display()
        # dynamics.cumulative_volatility.display()
        #dynamics.cumulative_volatility.movements.plot()

        print(rental_market_dynamics.volatility_frame.start_date)
        print(rental_market_dynamics.volatility_frame.end_date)
        # print(dynamics.volatility_frame.aggregation)
        rental_market_dynamics.volatility_frame.display()

        plt.show(block=True)

        rent_cycle_period_avg = 10.
        cyclicality_params = {
            # In the U.S. the real estate market cycle seems to be in the range of 10 to 20 years.
            # This will randomly generate the cycle period governing each future history to be between 10 and 20 years.
            'rent_cycle_period_mean': rent_cycle_period_avg,
            'rent_cycle_period_error': 10.,


            # If you make this equal to a uniform random variable times the rent cycle period
            # then the phase will range from starting anywhere from peak to trough with equal likelihood.
            # E.g.:
            # 'rent_cycle_phase_mean' = distribution.Uniform().sample() * rent_cycle_period_avg,
            #
            # If you think you know where you are in the cycle, then use this relationship of Phase to Cycle Period:
            # Phase=:             Cycle:
            # (1/4)Period   = Bottom of cycle, headed up.
            # (1/2)Period   = Mid-cycle, headed down.
            # (3/4)Period   = Top of cycle, headed down.
            # (1/1)Period   = Mid-cycle, headed up.
            #
            # Example, if you enter 20 in cycle period, and you enter 5 in cycle phase,
            # then the cycle will be starting out in the first year at the bottom of the cycle, heading up from there.
            #
            # Please note that with the compound-sine asymetric cycle formula,
            # the peak parameter is slightly off from the above; 0.65*Period seems to start the cycle closer to the peak.
            # For example, if you want the phase to vary randomly and uniformly over the 1/8 of the cycle
            # that is the top of the upswing (late boom just before downturn),
            # you would enter: .175 * distribution.Uniform().sample() +.65 * rent_cycle_period_avg
            'rent_cycle_phase_mean': .175 * distribution.Uniform().sample() +.65 * rent_cycle_period_avg,
            'rent_cycle_phase_error': 1.,

            'rent_cycle_amp_mean': .15,
            'rent_cycle_amp_error': .025,

            # The Cap Rate period can be randomly different from rent cycle period,
            # but probably not too different, maybe +/- 1 year.
            'cap_rate_period_mean': rent_cycle_period_avg,
            'cap_rate_period_error': 1.,

            # This cap rate cycle input is the negative of the actual cap rate cycle,
            # you can think of the phase in the same way as the space market phase.
            # These two cycles are not generally exactly in sync, but the usually are not too far off.
            # Hence, probably makes sense to set this asset market phase equal to the space market phase
            # +/- some random difference that is a pretty small fraction of the cycle period.
            # Remember that peak-to-trough is half period, LR mean to either peak or trough is quarter period.
            # E.g.: rent_cycle_phase + (distribution.Uniform().sample() * cap_rate_cycle_period/5) - cap_rate_cycle_period/10
            # Above would let asset phase differ from space phase by +/- a bit less than a quarter-period (here, a fifth of the asset cycle period).
            'cap_rate_phase_mean': rent_cycle_period_avg

            









