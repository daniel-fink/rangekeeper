from __future__ import annotations

import pandas as pd

import rangekeeper as rk


class Noise:
    def __init__(
            self,
            sequence: pd.PeriodIndex,
            noise_dist: rk.distribution.Form):
        """
        Note that a random realization of noise is generated each period, but it is applied to the value
        LEVELs (not to the returns or increments), hence, noise does not
        accumulate over time in the levels (unlike volatility). In actuality
        noise would be "realized" only when/if the asset is sold, or its value
        is formally estimated. But of course, in principle, an asset sale
        (or formal value estimation) could take place at any time.

        In this column the noise we generated in the previous column is
        applied to the noise-free value history in the "TrueValue" column,
        to generate the actually-observable value each year (excluding any
        "black swan" impact).
        """
        self.sequence = sequence
        self.noise_dist = noise_dist

    def generate(self) -> rk.flux.Flow:
        return rk.flux.Flow(
            movements=pd.Series(
                data=self.noise_dist.sample(size=self.sequence.size),
                index=rk.duration.Sequence.to_datestamps(sequence=self.sequence)),
            name='Noise')
