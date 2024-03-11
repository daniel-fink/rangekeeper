from __future__ import annotations

import numpy as np
import pandas as pd
from numba import jit

import rangekeeper as rk


class BlackSwan:
    def __init__(
            self,
            sequence: pd.PeriodIndex,
            likelihood: float,
            dissipation_rate: float,
            probability: rk.distribution.Form,
            impact: float):
        """
        This random variable will determine whether a "black swan" event
        occurs in any given year. We ensure that no more than one black
        swan will occur in the 24-yr history, as black swans are by definition
        rare events.

        This column causes the effect of the Black Swan event to dissipate
        over time, geometrically, at the same mean reversion rate as is
        applied in general to the rents (entered in co.F).

        This is another source or type of uncertainty in real estate pricing.
        This will apply the given "black swan" result, but then reduces
        the subsequent impact of the event gradually as mean-reversion
        takes effect.
        """
        self.sequence = sequence
        self.likelihood = likelihood
        self.dissipation_rate = dissipation_rate
        self.probability = probability
        self.impact = impact

    def generate(self) -> rk.flux.Flow:
        return rk.flux.Flow(
            name='Black Swan Effect',
            movements=pd.Series(
                data=self.calculate_black_swan_effects(
                    likelihood=self.likelihood,
                    dissipation_rate=self.dissipation_rate,
                    events=self.probability.sample(self.sequence.size)),
                index=rk.duration.Sequence.to_datestamps(sequence=self.sequence)))

    @staticmethod
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
