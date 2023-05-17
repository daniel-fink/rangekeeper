from __future__ import annotations
import os

from typing import Generator
import copy

import numpy as np
import pandas as pd
from numba import jit
import multiprocess

import rangekeeper as rk


class Market:
    def __init__(
            self,
            sequence: pd.PeriodIndex,
            trend: rk.dynamics.trend.Trend,
            volatility: rk.dynamics.volatility.Volatility,
            cyclicality: rk.dynamics.cyclicality.Cyclicality,
            noise: rk.dynamics.noise.Noise,
            black_swan: rk.dynamics.black_swan.BlackSwan):
        """

        """
        self.sequence = sequence
        self._sequence = rk.periodicity.offset_periodindex(
            index=self.sequence,
            offset_end=-1)

        self.trend = trend
        self.volatility = volatility
        self.cyclicality = cyclicality

        self.space_market = rk.flux.Flow(
            movements=(
                        self.cyclicality.space_waveform.movements * self.volatility.movements),
            name='Space Market')

        self.asset_market = rk.flux.Flow(
            movements=self.trend.cap_rate - self.cyclicality.asset_waveform.movements,
            name='Asset Market')
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

        self.asset_true_value = rk.flux.Flow(
            movements=self.space_market.movements / self.asset_market.movements,
            name='Asset True Value')
        """
        This applies the capital market cycle to the rent history to obtain 
        the history of "true values," that is, the asset values (PVs) that 
        would prevail if there were no "noise" (transaction or observation
        "error"), and at this point also ignoring "black swan" events.
        """

        self.space_market_price_factors = rk.flux.Flow(
            movements=self.space_market.movements / self.trend.initial_value,
            name='Space Market Price Factors')
        """
        This is the "true value" pricing factor for just the space market, 
        not reflecting the asset market cycle (cap rate). We have actually 
        already computed this, and we're here just making it into a ratio
        of the initial rent. This series of Pricing factors will apply to 
        operating cash flows.
        """

        self.noise = noise
        self.noisy_value = rk.flux.Flow(
            movements=(1 + self.noise.generate().movements) * self.asset_true_value.movements,
            name='Noisy Value')

        self.black_swan = black_swan
        self.historical_value = rk.flux.Flow(
            movements=self.noisy_value.movements * (1 + self.black_swan.impact * self.black_swan.generate().movements),
            name='Historical Value')

        implied_cap_rate_data = (self.space_market.movements[1:].reset_index(drop=True) /
                                 self.historical_value.movements[:-1].reset_index(drop=True))
        # implied_cap_rate_data = pd.concat([implied_cap_rate_data, pd.Series(np.nan)], axis=0, join='outer')
        self.implied_rev_cap_rate = rk.flux.Flow(
            movements=pd.Series(
                data=implied_cap_rate_data.values,
                index=rk.periodicity.to_datestamps(period_index=self._sequence)),
            name='Implied Cap Rate')
        """
        These are the forward-looking cap rates implied for each year of the 
        scenario. These will govern the reversion (resale) cash flows in the 
        DCF model of PV.
        """

        returns_data = (self.historical_value.movements[1:].reset_index(drop=True) /
                        self.historical_value.movements[:-1].reset_index(drop=True)) - 1
        # returns_data = pd.concat([returns_data, pd.Series(np.nan)], axis=0, join='outer')
        self.returns = rk.flux.Flow(
            movements=pd.Series(
                data=returns_data.values,
                index=rk.periodicity.to_datestamps(period_index=self._sequence)),
            name='Returns')

        """
        This is the implied capital returns series for the scenario. It reflects
        the overall pricing dynamics and uncertainty in the property value over 
        time.        
        """

    @classmethod
    def _from_args(
            cls,
            args: tuple) -> Market:
        sequence, trend, volatility, cyclicality, noise, black_swan = args
        return cls(
            sequence=sequence,
            trend=trend,
            volatility=volatility,
            cyclicality=cyclicality,
            noise=noise,
            black_swan=black_swan)

    @classmethod
    def from_likelihoods(
            cls,
            sequence: pd.PeriodIndex,
            trends: [rk.dynamics.trend.Trend],
            volatilities: [rk.dynamics.volatility.Volatility],
            cyclicalities: [rk.dynamics.cyclicality.Cyclicality],
            noise: rk.dynamics.noise.Noise,
            black_swan: rk.dynamics.black_swan.BlackSwan) -> [Market]:

        pool = multiprocess.Pool(os.cpu_count())

        args = [(sequence, trend, volatility, cyclicality, noise, black_swan)
            for (trend, volatility, cyclicality)
            in zip(trends, volatilities, cyclicalities)]

        return pool.map(cls._from_args, args)

    # def __init__(
    #         self,
    #         sequence: pd.PeriodIndex,
    #         market_params: dict,
    #         volatility_params: dict,
    #         cyclicality_params: dict):
    #     """
    #
    #     """
    #     self.span = rk.periodicity.to_span(period_index=sequence)
    #     self._sequence = rk.periodicity.offset_periodindex(
    #         index=sequence,
    #         offset_end=-1)
    #
    #     self.trend = market_params['trend']
    #     self.initial_rent = market_params['initial_rent']
    #     self.market_trend = rk.flux.Flow.from_projection(
    #         name='Market Trend',
    #         value=self.initial_rent,
    #         proj=rk.projection.Extrapolation(
    #             form=self.trend,
    #             sequence=sequence))
    #
    #     self.market_volatility = rk.dynamics.volatility.Volatility(
    #         trend=self.trend,
    #         initial_rent=self.initial_rent,
    #         volatility_per_period=volatility_params['volatility_per_period'],
    #         mean_reversion_param=volatility_params['mean_reversion_param'],
    #         autoregression_param=volatility_params['autoregression_param'],
    #         sequence=sequence)
    #
    #     self.market_cyclicality = rk.dynamics.cyclicality.Cyclicality(
    #         space_cycle_period=cyclicality_params['space_cycle_period'],
    #         space_cycle_phase=cyclicality_params['space_cycle_phase'],
    #         space_cycle_amplitude=cyclicality_params['space_cycle_amplitude'],
    #         space_cycle_asymmetric_parameter=cyclicality_params['space_cycle_asymmetric_parameter'],
    #         asset_cycle_period=cyclicality_params['asset_cycle_period'],
    #         asset_cycle_phase=cyclicality_params['asset_cycle_phase'],
    #         asset_cycle_amplitude=cyclicality_params['asset_cycle_amplitude'],
    #         asset_cycle_asymmetric_parameter=cyclicality_params['asset_cycle_asymmetric_parameter'],
    #         sequence=sequence)
    #
    #     self.space_market = rk.flux.Flow(
    #         movements=(
    #                     self.market_cyclicality.space_waveform.movements * self.market_volatility.cumulative_volatility.movements),
    #         name='Space Market')
    #
    #     self.asset_market = rk.flux.Flow(
    #         movements=market_params['cap_rate'] - self.market_cyclicality.asset_waveform.movements,
    #         name='Asset Market')
    #     """
    #     Negative of actual cap rate cycle.
    #     This makes this cycle directly reflect the asset pricing, as prices
    #     are an inverse function of the cap rate. By taking the negative of the
    #     actual cap rate, we therefore make it easier to envision the effect
    #     on prices.
    #
    #     We're subtracting the cap rate cycle from the long-term mean cap rate,
    #     rather than adding it, because we're entering the cap rate cycle
    #     negative to the actual cap rate cycle, so that the cycle is up when
    #     prices are up and down when prices are down. Recall that the actual
    #     cap rate is inversely related to prices
    #     (high cap rates ==> low prices & vice versa).
    #
    #     It's easier to think about cycles positively.
    #     """
    #
    #     self.asset_true_value = rk.flux.Flow(
    #         movements=self.space_market.movements / self.asset_market.movements,
    #         name='Asset True Value')
    #     """
    #     This applies the capital market cycle to the rent history to obtain
    #     the history of "true values," that is, the asset values (PVs) that
    #     would prevail if there were no "noise" (transaction or observation
    #     "error"), and at this point also ignoring "black swan" events.
    #     """
    #
    #     self.space_market_price_factors = rk.flux.Flow(
    #         movements=self.space_market.movements / self.initial_rent,
    #         name='Space Market Price Factors')
    #     """
    #     This is the "true value" pricing factor for just the space market,
    #     not reflecting the asset market cycle (cap rate). We have actually
    #     already computed this, and we're here just making it into a ratio
    #     of the initial rent. This series of Pricing factors will apply to
    #     operating cash flows.
    #     """
    #
    #     self.noise_values = [rk.distribution.Symmetric(
    #         distribution_type=rk.distribution.Type.PERT,
    #         mean=0.,
    #         residual=market_params['noise_residual']
    #         ).distribution().sample() for _ in range(sequence.size)]
    #     self.noise = rk.flux.Flow(
    #         movements=pd.Series(
    #             data=self.noise_values,
    #             index=rk.periodicity.to_datestamps(period_index=sequence)),
    #         name='Noise')
    #     """
    #     This is a symmetric PERT distribution. Note that a random realization
    #     of noise is generated each period, but it is applied to the value
    #     LEVELs (not to the returns or increments), hence, noise does not
    #     accumulate over time in the levels (unlike volatility). In actuality
    #     noise would be "realized" only when/if the asset is sold, or its value
    #     is formally estimated. But of course, in principle, an asset sale
    #     (or formal value estimation) could take place at any time.
    #     """
    #
    #     self.noisy_value = rk.flux.Flow(
    #         movements=(1 + self.noise.movements) * self.asset_true_value.movements,
    #         name='Noisy Value')
    #     """
    #     In this column the noise we generated in the previous column is
    #     applied to the noise-free value history in the "TrueValue" column,
    #     to generate the actually-observable value each year (excluding any
    #     "black swan" impact).
    #     """
    #
    #     black_swan_effect_data = pd.Series(
    #         data=self.calculate_black_swan_effects(
    #             likelihood=market_params['black_swan_likelihood'],
    #             dissipation_rate=market_params['black_swan_dissipation_rate'],
    #             events=market_params['black_swan_prob_dist'].sample(sequence.size)),
    #         index=rk.periodicity.to_datestamps(period_index=sequence))
    #     self.black_swan_effect = rk.flux.Flow(
    #         movements=black_swan_effect_data,
    #         name='Black Swan Effect')
    #     """
    #     This random variable will determine whether a "black swan" event
    #     occurs in any given year. We ensure that no more than one black
    #     swan will occur in the 24-yr history, as black swans are by definition
    #     rare events.
    #
    #     This column causes the effect of the Black Swan event to dissipate
    #     over time, geometrically, at the same mean reversion rate as is
    #     applied in general to the rents (entered in co.F).
    #     """
    #
    #     self.historical_value = rk.flux.Flow(
    #         movements=self.noisy_value.movements * (
    #                 1 + market_params['black_swan_impact'] * self.black_swan_effect.movements),
    #         name='Historical Value')
    #     """
    #     This is another source or type of uncertainty in real estate pricing.
    #     This column will apply the given "black swan" result, but then reduces
    #     the subsequent impact of the event gradually as mean-reversion
    #     takes effect.
    #     """
    #
    #     implied_cap_rate_data = (self.space_market.movements[1:].reset_index(drop=True) /
    #                              self.historical_value.movements[:-1].reset_index(drop=True))
    #     # implied_cap_rate_data = pd.concat([implied_cap_rate_data, pd.Series(np.nan)], axis=0, join='outer')
    #     self.implied_rev_cap_rate = rk.flux.Flow(
    #         movements=pd.Series(
    #             data=implied_cap_rate_data.values,
    #             index=rk.periodicity.to_datestamps(period_index=self._sequence)),
    #         name='Implied Cap Rate')
    #     """
    #     These are the forward-looking cap rates implied for each year of the
    #     scenario. These will govern the reversion (resale) cash flows in the
    #     DCF model of PV.
    #     """
    #
    #     returns_data = (self.historical_value.movements[1:].reset_index(drop=True) /
    #                     self.historical_value.movements[:-1].reset_index(drop=True)) - 1
    #     # returns_data = pd.concat([returns_data, pd.Series(np.nan)], axis=0, join='outer')
    #     self.returns = rk.flux.Flow(
    #         movements=pd.Series(
    #             data=returns_data.values,
    #             index=rk.periodicity.to_datestamps(period_index=self._sequence)),
    #         name='Returns')
    #
    #     """
    #     This is the implied capital returns series for the scenario. It reflects
    #     the overall pricing dynamics and uncertainty in the property value over
    #     time.
    #     """
