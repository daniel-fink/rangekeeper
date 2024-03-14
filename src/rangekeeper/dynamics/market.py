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
        self._sequence = rk.duration.Sequence.extend(
            sequence=self.sequence,
            end_offset=-1)

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
                index=rk.duration.Sequence.to_datestamps(sequence=self._sequence)),
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
                index=rk.duration.Sequence.to_datestamps(sequence=self._sequence)),
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
