import numpy as np
import pandas as pd
from numba import jit

import distribution
import flux
import units
from dynamics import trend, volatility, cyclicality


class Market:
    def __init__(self,
                 params: dict,
                 trend: trend.Trend,
                 volatility: volatility.Volatility,
                 cyclicality: cyclicality.Cyclicality):
        """

        :param params:
        :type params:
        :param cyclicality:
        :type cyclicality:
        :param index:
        :type index:
        """

        self.space_market = flux.Flow(
            movements=(cyclicality.space_waveform.movements * volatility.cumulative_volatility.movements),
            units=units.Units.Type.scalar,
            name='space_market')

        self.asset_market = flux.Flow(
            movements=params['cap_rate'] - cyclicality.asset_waveform.movements,
            units=units.Units.Type.scalar,
            name='asset_market')
        """
        Negative of actual cap rate cycle. 
        This makes this cycle directly reflect the asset pricing, as prices 
        are an inverse function of the cap rate. By taking the negative of the 
        actual cap rate, we therefore make it easier to envision the effect 
        on prices.

        We're subtracting the cap rate cycle from the long-term mean cap rate, 
        rather than adding it, because we're entering the cap rate cycle 
        negative to the actual cap rate cycle, so that the cycle is up when 
        prices are up and down when prices are down. Recall that the actual 
        cap rate is inversely related to prices 
        (high cap rates ==> low prices & vice versa). 

        It's easier to think about cycles positively.
        """

        self.asset_true_value = flux.Flow(
            movements=self.space_market.movements / self.asset_market.movements,
            units=units.Units.Type.scalar,
            name='Asset True Value')
        """
        This applies the capital market cycle to the rent history to obtain 
        the history of "true values," that is, the asset values (PVs) that 
        would prevail if there were no "noise" (transaction or observation
        "error"), and at this point also ignoring "black swan" events.
        """

        self.space_market_price_factors = flux.Flow(
            movements=self.space_market.movements / trend.current_rent,
            units=units.Units.Type.scalar,
            name='Space Market Price Factors')
        """
        This is the "true value" pricing factor for just the space market, 
        not reflecting the asset market cycle (cap rate). We have actually 
        already computed this, and we're here just making it into a ratio
        of the initial rent. This series of Pricing factors will apply to 
        operating cash flows.
        """

        self.noise_values = [distribution.Symmetric(
            distribution_type=distribution.Type.PERT,
            mean=0.,
            residual=params['noise_residual']
            ).distribution().sample() for _ in range(trend.trend.movements.index.size)]
        self.noise = flux.Flow(
            movements=pd.Series(
                data=self.noise_values,
                index=trend.trend.movements.index),
            units=units.Units.Type.scalar,
            name='Noise')
        """
        This is a symmetric PERT distribution. Note that a random realization
        of noise is generated each period, but it is applied to the value
        LEVELs (not to the returns or increments), hence, noise does not
        accumulate over time in the levels (unlike volatility). In actuality
        noise would be "realized" only when/if the asset is sold, or its value
        is formally estimated. But of course, in principle, an asset sale
        (or formal value estimation) could take place at any time.
        """

        self.noisy_value = flux.Flow(
            movements=(1 + self.noise.movements) * self.asset_true_value.movements,
            units=units.Units.Type.scalar,
            name='Noisy Value')
        """
        In this column the noise we generated in the previous column is
        applied to the noise-free value history in the "TrueValue" column,
        to generate the actually-observable value each year (excluding any
        "black swan" impact).
        """

        @jit(nopython=True)
        def calculate_black_swan_effects(
                likelihood: float,
                dissipation_rate: float,
                events: [float]):
            """

            :param likelihood:
            :type likelihood:
            :param dissipation_rate:
            :type dissipation_rate:
            :param events:
            :type events:
            :return:
            :rtype:
            """
            idx = -1
            impacts = []
            for i in range(len(events)):
                if idx == -1:
                    if events[i] < likelihood:
                        idx = i
                        impacts.append(1)
                    else:
                        impacts.append(0)
                else:
                    impacts.append(np.power((1 - dissipation_rate), (i - idx)))
            return impacts

        black_swan_effect_data = pd.Series(
            data=calculate_black_swan_effects(
                likelihood=params['black_swan_likelihood'],
                dissipation_rate=params['black_swan_dissipation_rate'],
                events=params['black_swan_prob_dist'].sample(trend.trend.movements.index.size)),
            index=trend.trend.movements.index)
        self.black_swan_effect = flux.Flow(
            movements=black_swan_effect_data,
            units=units.Units.Type.scalar,
            name='Black Swan Effect')
        """
        This random variable will determine whether a "black swan" event
        occurs in any given year. We ensure that no more than one black
        swan will occur in the 24-yr history, as black swans are by definition
        rare events.

        This column causes the effect of the Black Swan event to dissipate
        over time, geometrically, at the same mean reversion rate as is
        applied in general to the rents (entered in co.F).
        """

        self.historical_value = flux.Flow(
            movements=self.noisy_value.movements * (1 + params['black_swan_impact'] * self.black_swan_effect.movements),
            units=units.Units.Type.scalar,
            name='Historical Value')
        """
        This is another source or type of uncertainty in real estate pricing.
        This column will apply the given "black swan" result, but then reduces
        the subsequent impact of the event gradually as mean-reversion
        takes effect.
        """


