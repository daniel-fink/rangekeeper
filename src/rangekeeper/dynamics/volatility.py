from __future__ import annotations
import os

from typing import Generator, Optional, Sequence
import numpy as np
import pandas as pd
import scipy as sp
from numba import jit
import numba
import multiprocess

import rangekeeper as rk


class Volatility(rk.flux.Flow):
    def __init__(
            self,
            trend: rk.dynamics.trend.Trend,
            volatility_per_period: float,
            autoregression_param: float,
            mean_reversion_param: float,
            sequence: pd.PeriodIndex,
            generator: Optional[np.random.Generator] = None):
        """
        This is a normal (Gaussian) distribution.
        Note that volatility is realized (new random increment is generated) in EACH period,
        so that this "risk" outcome accumulates in the history of rent levels.
        But this is just the volatility in the innovations; if there is autoregression then that will also affect the annual volatility.
        Cycles will also affect the average volatility observed empirically across the scenario.
        volatility_per_period = .08

        generator: an optional numpy random Generator that draws the innovations (one draw per period, in order).
        Pass a seeded generator (for example np.random.default_rng(42)) to make the volatility, and so a Market
        built from it, reproducible. If None (the default), each draw uses a fresh unseeded generator, as before.
        """

        volatilities = pd.Series(
            data=[sp.special.ndtri(
                      rk.distribution.Uniform(lower=0, range=1, generator=generator).sample()[0]
                  ) * volatility_per_period
                  for x in range(sequence.size)],
            # the ndtri() function replicates excel's NORMSINV().
            # See https://stackoverflow.com/questions/20626994/how-to-calculate-the-inverse-of-the-normal-cumulative-distribution-function-in-p/20627638
            index=rk.duration.Sequence.to_datestamps(sequence=sequence))

        self.volatility = rk.flux.Flow(
            movements=volatilities,
            name='Volatility')

        volatility = numba.typed.List()
        [volatility.append(x) for x in self.volatility.movements.to_list()]

        autoregression_return_data = self.calculate_autoregression(
            parameter=autoregression_param,
            volatility=volatility)
        self.autoregressive_returns = rk.flux.Flow(
            movements=pd.Series(
                data=autoregression_return_data,
                index=self.volatility.movements.index),
            name='Autoregressive Returns')

        trend_values = numba.typed.List()
        [trend_values.append(x) for x in trend.movements.to_list()]

        ar_returns = numba.typed.List()
        [ar_returns.append(x) for x in self.autoregressive_returns.movements.to_list()]

        cumulative_volatility_data = self.calculate_volatility_accumulation(
            trend_rate=trend.growth_rate,
            trend_values=trend_values,
            mr_parameter=mean_reversion_param,
            ar_returns=ar_returns)

        movements = pd.Series(
                data=cumulative_volatility_data,
                index=rk.duration.Sequence.to_datestamps(sequence=sequence))

        super().__init__(
            name='Cumulative Volatility',
            movements=movements)

    @classmethod
    def _from_args(
            cls,
            args: tuple) -> Volatility:
        trend, volatility_per_period, autoregression_param, mean_reversion_param, sequence, generator = args
        return cls(
            trend=trend,
            volatility_per_period=volatility_per_period,
            autoregression_param=autoregression_param,
            mean_reversion_param=mean_reversion_param,
            sequence=sequence,
            generator=generator)

    @classmethod
    def from_trends(
            cls,
            trends: [rk.dynamics.trend.Trend],
            volatility_per_period: float,
            autoregression_param: float,
            mean_reversion_param: float,
            sequence: pd.PeriodIndex,
            seed: Optional[int] = None) -> [Volatility]:
        """
        seed: if given, each Volatility gets its own independent generator spawned from this seed
        (np.random.SeedSequence), so the result is reproducible and the worker processes do not share a stream.
        If None (the default), the draws are unseeded, as before.
        """

        pool = multiprocess.Pool(os.cpu_count())

        generators: Sequence[Optional[np.random.Generator]] = (
            [None] * len(trends) if seed is None
            else [np.random.default_rng(child) for child in np.random.SeedSequence(seed).spawn(len(trends))])

        args = [
            (trend,
             volatility_per_period,
             autoregression_param,
             mean_reversion_param,
             sequence,
             generator)
            for trend, generator in zip(trends, generators)]

        return pool.map(cls._from_args, args)

    @staticmethod
    @jit(nopython=True)
    def calculate_autoregression(
            parameter: float,
            volatility: numba.typed.List):
        ar_returns = numba.typed.List()
        for i in range(len(volatility)):
            if i == 0:
                ar_returns.append(volatility[0])
            else:
                ar_returns.append(volatility[i] + (parameter * ar_returns[i - 1]))
        return ar_returns

    @staticmethod
    @jit(nopython=True)
    def calculate_volatility_accumulation(
            trend_rate: float,
            trend_values: numba.typed.List,
            mr_parameter: float,
            ar_returns: numba.typed.List):
        """
        Cumulative Volatility:
        Accumulate the volatility generated in the previous column, also reflecting the mean reversion tendency.
        """
        accumulated_volatility = numba.typed.List()
        for i in range(len(trend_values)):
            if i == 0:
                accumulated_volatility.append(trend_values[0])
            else:
                accumulated_volatility.append(
                    (accumulated_volatility[i - 1] * (1 + trend_rate + ar_returns[i])) +
                    (mr_parameter * (trend_values[i - 1] - accumulated_volatility[i - 1]))
                    )
        return accumulated_volatility
