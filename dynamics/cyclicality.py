import math

import pandas as pd
import scipy as sp
import numpy as np
from numba import jit
import typing

import distribution, flux, phase, periodicity, units


class DistributionParams:
    def __init__(self,
                 distribution_type: distribution.Type,
                 mean: float,
                 residual: float = 0.,
                 generator: typing.Optional[np.random.Generator] = None):
        """
        Parameters that define the mean and residual (maximum deviation)
        of a symmetric distribution
        """
        self.mean = mean
        self.residual = residual
        if distribution_type == distribution.Type.uniform | distribution_type == distribution.Type.PERT:
            self.distribution_type = distribution_type
        else:
            raise ValueError("Distribution type must be symmetrical about its mean")
        self.generator = generator

    def distribution(self):
        if self.distribution_type == distribution.Type.uniform:
            return distribution.Uniform(mean=self.mean,
                                        scale=self.residual * 2,
                                        generator=self.generator)
        elif self.distribution_type == distribution.Type.PERT:
            return distribution.PERT.standard_symmetric(peak=self.mean,
                                                        residual=self.residual)


class Cycle:
    def __init__(self,
                 period: float,
                 phase: float,
                 amplitude: float):
        """
        Parameters that define a cyclical time series
        """
        self.period = period
        self.phase = phase
        self.amplitude = amplitude

    @jit(nopython=True)
    def sine(self,
             index: pd.PeriodIndex):
        """
        Generate a sine wave from the parameters.
        The conventional, symmetric cycle is a simple sine function, parameterized:
        y = amplitude * sin((t - phase) * (2 * pi / period))
        """
        data = []
        for i in range(index.size):
            data.append(self.amplitude *
                        np.sin(
                            (i - self.phase) *
                            (2 * np.pi / self.period)
                            )
                        )
        return pd.Series(data=data, index=index)

    @jit(nopython=True)
    def compound_sine(self,
                      offset: float,
                      index: pd.PeriodIndex):
        """
        Generate a compound (asymmetrically offset) sine wave from the parameters.
        The asymmetry is introduced to the cycle by compounding the sine function:
        y = amplitude * sin((t - phase) - (a * period) * sin((t - phase) * 2 * pi / period)) * 2 * pi / period),
        where a is a small fraction 0 < a < 1.
        e.g. a = 0.1 will produce a downturn approx. 0.5 * duration of the up-swing.
        """
        data = []
        for i in range(index.size):
            data.append(self.amplitude *
                        np.sin(
                            (i - self.phase) - (offset * self.period) *
                            np.sin(
                                (i - self.phase) *
                                (2 * np.pi / self.period)
                                ) *
                            (2 * np.pi / self.period)
                            )
                        )
        return pd.Series(data=data, index=index)


class Market:
    def __init__(self,
                 params: dict):
        rent_period = DistributionParams(params['rent_cycle_period_mean'],
                                         params['rent_cycle_period_residual'],
                                         params['rent_cycle_period_dist']).distribution().sample()
        """
        In the U.S. the real estate market cycle seems to be in the range of 10 to 20 years. 
        E.g.:
        =RAND()*10+10
        This will randomly generate the cycle period governing each
        future history to be between 10 and 20 years.
        """

        rent_phase = (DistributionParams(params['rent_cycle_phase_offset'],
                                        params['rent_cycle_phase_residual'],
                                        params['rent_cycle_phase_dist']).distribution().sample() + .65) * rent_period
        """
        If you make this equal to a uniform RV times the rent cycle period 
        then the phase will range from starting anywhere from peak to trough with equal likelihood.
        E.g.:
        =RAND()*J10, if the Period is in J10.
        
        If you think you know where you are in the cycle, 
        then use this relationship of Phase to Cycle Period:
        Phase=:             Cycle:
        (1/4)Period   = Bottom of cycle, headed up.
        (1/2)Period   = Mid-cycle, headed down.
        (3/4)Period   = Top of cycle, headed down.
        (1/1)Period   = Mid-cycle, headed up.
        
        Example, if you enter 20 in cycle period, and you enter 5 in cycle phase, 
        then the cycle will be starting out in the first year at the bottom of the cycle, 
        heading up from there.
        
        Please note that with the compound-sine asymetric cycle formula, 
        the peak parameter is slightly off from the above. 
        0.65*Period seems to start the cycle closer to the peak. 
        For example, if you want the phase to vary randomly and 
        uniformly over the 1/8 of the cycle that is the top of the upswing (late boom just before downturn),
        you would enter:
        =(.175*RAND()+.65)*J10, if Period is in J10.
        """
        rent_amplitude = DistributionParams(params['rent_cycle_ampltiude_mean'],
                                            params['rent_cycle_ampltiude_residual'],
                                            params['rent_cycle_ampltiude_dist']).distribution().sample()

        self.rent_cycle = Cycle(period=rent_period,
                                phase=rent_phase,
                                amplitude=rent_amplitude)

        caprate_period = DistributionParams(params['caprate_cycle_period_offset'],
                                            params['caprate_cycle_period_residual'],
                                            params['caprate_cycle_period_dist']).distribution().sample() + rent_period
        """
        This  can be randomly different from rent cycle period, 
        but probably not too different, maybe +/- 1 year.
        E.g.:
        =J10+(RAND()*2-1)
        """

        caprate_phase = DistributionParams(params['caprate_cycle_phase_offset'],
                                           params['caprate_cycle_phase_residual'],
                                           params['caprate_cycle_phase_dist']).distribution().sample() * caprate_period + rent_phase
        """
        Since we input this cycle as the negative of the actual cap rate cycle, 
        you can think of the phase in the same way as the space market phase. 
        These two cycles are not generally exactly in sync, but the usually are not too far off.
        Hence, probably makes sense to set this asset market phase 
        equal to the space market phase +/- some random difference 
        that is a pretty small fraction of the cycle period. 
        Remember that peak-to-trough is half period, LR mean to either peak or trough is quarter period. 
        E.g.: =J8+(RAND()*J11/5-J11/10)
        Above would let asset phase differ from space phase by +/- a bit less than a quarter-period 
        (here, a fifth of the asset cycle period).
        """

        caprate_amplitude = DistributionParams(params['caprate_cycle_ampltiude_mean'],
                                               params['caprate_cycle_ampltiude_residual'],
                                               params['caprate_cycle_ampltiude_dist']).distribution().sample()
        """
        This is in cap rate units, so keep in mind the magnitude of the initial cap rate 
        entered on the MktDynamicsInputs sheet. 
        For example, if the initial (base) cap rate entered there is 5.00%, 
        and you enter 2.00% here, then this will mean a cap rate cycle 
        swinging between 4.00% & 6.00%, which corresponds roughly to 
        a property value swing of +/-20% (other things equal). 
        Note also that because this cycle is symmetric 
        but operates in the denominator of the pricing factors governing the simulated future cash flows, 
        this cycle imparts a positive bias into the project ex post cash flows 
        relative to the proforma expected cash flows.
        """

        self.caprate_cycle = Cycle(period=caprate_period,
                                   phase=caprate_phase,
                                   amplitude=caprate_amplitude)