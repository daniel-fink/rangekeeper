from __future__ import annotations
import os

from typing import Optional, Generator

import pandas as pd
import multiprocess

import rangekeeper as rk


class Trend(rk.flux.Flow):
    growth_rate: float
    cap_rate: float
    initial_value: float
    initial_price_factor: float

    def __init__(
            self,
            sequence: pd.PeriodIndex,
            growth_rate: float,
            cap_rate: float,
            initial_value: Optional[float] = None,
            initial_price_factor: float = 1.):
        self.sequence = sequence
        self.cap_rate = cap_rate
        self.growth_rate = growth_rate
        self.initial_value = initial_price_factor * self.cap_rate if initial_value is None else initial_value
        self.initial_price_factor = initial_price_factor

        self.proj = rk.projection.Extrapolation(
            form=rk.extrapolation.Compounding(rate=self.growth_rate),
            sequence=self.sequence)

        super().__init__(
            name='Market Trend',
            movements=self.proj.terms() * self.initial_value)

    @classmethod
    def _from_args(
            cls,
            args: tuple) -> Trend:
        sequence, cap_rate, growth_rate, initial_value, initial_price_factor = args
        return cls(
            sequence=sequence,
            cap_rate=cap_rate,
            growth_rate=growth_rate,
            initial_value=initial_value,
            initial_price_factor=initial_price_factor)
    @classmethod
    def from_likelihoods(
            cls,
            sequence: pd.PeriodIndex,
            cap_rate: float,
            growth_rate_dist: rk.distribution,
            initial_value_dist: rk.distribution,
            initial_price_factor: float = 1.,
            iterations: int = 1) -> [Trend]:
        growth_rates = growth_rate_dist.sample(size=iterations)
        initial_values = initial_value_dist.sample(size=iterations)

        pool = multiprocess.Pool(os.cpu_count())

        args = [
            (sequence,
             cap_rate,
             growth_rate,
             initial_value,
             initial_price_factor)
            for (growth_rate, initial_value)
            in zip(growth_rates, initial_values)
            ]

        results = pool.map(cls._from_args, args)
        if iterations == 1:
            return results[0]
        else:
            return results

