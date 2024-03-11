from __future__ import annotations
import os
import math
from typing import Generator

import numpy as np
import pandas as pd
from numba import jit
import multiprocess

import rangekeeper as rk


class Enumerate:
    @staticmethod
    # @jit(nopython=True)
    def sine(
            period: float,
            phase: float,
            amplitude: float,
            num_periods: int):
        """
        Generate a sine wave from the parameters.
        The conventional, symmetric cycle is a simple sine function, parameterized:
        y = amplitude * sin((t - phase) * (2 * pi / period))
        """
        data = []
        for i in range(num_periods):
            data.append(amplitude *
                        np.sin(
                            (i - phase) *
                            (2 * np.pi / period)
                            )
                        )
        return data

    @staticmethod
    def asymmetric_sine(
            period: float,
            phase: float,
            amplitude: float,
            parameter: float,
            num_periods: int,
            precision: float,
            bound: float):
        """
        Generate a smoothed sinusoid asymmetric (sawtooth) wave.
        Based on the solution to the expression: f(x) = sin(x - f(x)),
        with additional parameterization of period, phase, amplitude, and shear,
        where shear is defined as a parameter between 0 and 1 (1 being most asymmetric)

        Because the formula is recursive, we approximate the solution by
        solving sin(x + c) - x = 0, for x, as in this answer https://math.stackexchange.com/a/2645080
        to https://math.stackexchange.com/q/2644982/999815
        """

        if parameter == 0:
            return Enumerate.sine(
                period=period,
                phase=phase,
                amplitude=amplitude,
                num_periods=num_periods)

        @jit(nopython=True)
        def f(x):
            upper = 1 + bound
            lower = -upper
            while upper - lower > precision:
                mid = (lower + upper) / 2
                if -math.sin((x - phase) * (2 * np.pi / period) + mid) - ((1 / parameter) * mid) > 0:
                    lower = mid
                else:
                    upper = mid
            return (lower + upper) / 2 * (amplitude * (1 / -parameter))

        return list(map(f, range(num_periods)))


class Cycle:
    def __init__(
            self,
            period: float,
            phase: float,
            amplitude: float):
        """
        Parameters that define a cyclical time series
        """
        self.period = period
        self.phase = phase
        self.amplitude = amplitude

    def __str__(self):
        string = ""
        string += "Period: " + str(self.period) + "\n"
        string += "Phase: " + str(self.phase) + "\n"
        string += "Amplitude: " + str(self.amplitude) + "\n"
        return string

    def sine(
            self,
            sequence: pd.PeriodIndex,
            name: str = "sine_cycle"):
        data = Enumerate.sine(
            period=self.period,
            phase=self.phase,
            amplitude=self.amplitude,
            num_periods=sequence.size)
        return rk.flux.Flow(
            movements=pd.Series(
                data=data,
                index=rk.duration.Sequence.to_datestamps(sequence=sequence)),
            name=name)

    def asymmetric_sine(
            self,
            parameter: float,
            sequence: pd.PeriodIndex,
            precision: float = 1e-8,
            bound: float = 1e-1,
            name: str = "asymmetric_sine_cycle") -> rk.flux.Flow:
        data = Enumerate.asymmetric_sine(
            period=self.period,
            phase=self.phase,
            amplitude=self.amplitude,
            parameter=parameter,
            num_periods=sequence.size,
            precision=precision,
            bound=bound)
        return rk.flux.Flow(
            movements=pd.Series(
                data=data,
                index=rk.duration.Sequence.to_datestamps(sequence=sequence)),
            # units=measure.scalar,
            name=name)


class Cyclicality:
    space_waveform: rk.flux.Flow
    asset_waveform: rk.flux.Flow

    def __init__(
            self,
            sequence: pd.PeriodIndex,
            space_cycle: Cycle,
            asset_cycle: Cycle,
            space_cycle_asymmetric_parameter: float = None,
            asset_cycle_asymmetric_parameter: float = None):
        """
        This models a (possibly somewhat) predictable long-term cycle in the
        pricing. In fact, there are two cycles, not necessarily in sync,
        one for the space market (rents) and another separate cycle for the
        asset market (capital flows), the latter reflected by the cap rate.

        Cycles are modeled by generalized asymmetric sine functions.
        """
        self.space_cycle = space_cycle
        self.asset_cycle = asset_cycle

        if space_cycle_asymmetric_parameter == 0:
            space_waveform = self.space_cycle.sine(
                sequence=sequence,
                name='Space Cycle Waveform')
        else:
            space_waveform = self.space_cycle.asymmetric_sine(
                sequence=sequence,
                name='Space Cycle Waveform',
                parameter=space_cycle_asymmetric_parameter)
        self.space_waveform = rk.flux.Flow(
            name=space_waveform.name,
            movements=(1 + space_waveform.movements),
            units=space_waveform.units)

        if asset_cycle_asymmetric_parameter == 0:
            self.asset_waveform = self.asset_cycle.sine(
                sequence=sequence,
                name='Asset Cycle Waveform')
        else:
            self.asset_waveform = self.asset_cycle.asymmetric_sine(
                sequence=sequence,
                name='Asset Cycle Waveform',
                parameter=asset_cycle_asymmetric_parameter)

    @classmethod
    def from_params(
            cls,
            space_cycle_period: float,
            space_cycle_phase: float,
            space_cycle_amplitude: float,
            asset_cycle_period: float,
            asset_cycle_phase: float,
            asset_cycle_amplitude: float,
            space_cycle_asymmetric_parameter: float,
            asset_cycle_asymmetric_parameter: float,
            sequence: pd.PeriodIndex) -> Cyclicality:
        """
        This models a (possibly somewhat) predictable long-term cycle in the
        pricing. In fact, there are two cycles, not necessarily in sync,
        one for the space market (rents) and another separate cycle for the
        asset market (capital flows), the latter reflected by the cap rate.

        Cycles are modeled by generalized sine functions governed by the given
        input period, amplitude, and span.
        """

        space_cycle = Cycle(
            period=space_cycle_period,
            phase=space_cycle_phase,
            amplitude=space_cycle_amplitude)
        """
        In the U.S. the real estate market cycle period seems to be in the range of 10
        to 20 years. 
        
        
        The space cycle amplitude is modelled as a fraction of the mid-cycle 
        level. Historically in the U.S., such cycles in investment property have
        been as much as 50% or more in some locations in the rental market 
        (including both rent prices & occupancy effect and considering the
        leverage that fixed operating expenses have on the bottom-line net cash 
        flow). The Pricing Factors in this model apply to net cash flows, not 
        just top-line potential gross rental revenue.
        """

        asset_cycle = Cycle(
            period=asset_cycle_period,
            phase=asset_cycle_phase,
            amplitude=asset_cycle_amplitude)
        """
        Negative of actual cap rate cycle. This makes this cycle directly
        reflect the asset pricing, as prices are an inverse function of the 
        cap rate. By taking the negative of the actual cap rate, we therefore 
        make it easier to envision the effect on prices.
        
        Since we input this cycle as the negative of the actual cap rate cycle, 
        you can think of the phase in the same way as the space market phase. 
        """

        return cls(
            sequence=sequence,
            space_cycle=space_cycle,
            asset_cycle=asset_cycle,
            space_cycle_asymmetric_parameter=space_cycle_asymmetric_parameter,
            asset_cycle_asymmetric_parameter=asset_cycle_asymmetric_parameter)

    @classmethod
    def from_estimates(
            cls,
            space_cycle_phase_prop: float,
            space_cycle_period: float,
            space_cycle_height: float,
            asset_cycle_period_diff: float,
            asset_cycle_phase_diff_prop: float,
            asset_cycle_amplitude: float,
            space_cycle_asymmetric_parameter: float,
            asset_cycle_asymmetric_parameter: float,
            sequence: pd.PeriodIndex)  -> Cyclicality:

        space_cycle_phase = space_cycle_phase_prop * space_cycle_period
        """
        If you are agnostic about where the market currently is in the cycle, 
        and you want to simulate all possitilities, then make the space cycle 
        phase proportion a uniform random variable across the entire length of 
        the cycle period defined in the space_cycle_period input.        
        If you think you know where the market currently is in the cycle, then 
        specify the proportion of the cycle period to shift the cycle by (note, 
        since this is generated from a sine curve, the base (0) is at mid-cycle, 
        heading up. See https://en.wikipedia.org/wiki/Phase_(waves)
        """

        space_cycle_amplitude = space_cycle_height / 2
        """
        The space cycle height is the peak-to-trough full cycle amplitude as a 
        fraction of the mid-cycle level. Historically in the U.S. such cycles in
        investment property have been as much as 50% or more in some markets in 
        the rental market (including both rent prices & occupancy effect and 
        considering the leverage that fixed operating expenses have on the 
        bottom-line net cash flow). The Pricing Factors in this model apply to 
        net cash flows, not just top-line potential gross rental revenue.
        """

        asset_cycle_period = asset_cycle_period_diff + space_cycle_period
        """
        This can be randomly different from rent cycle period, but probably not
        too different, maybe +/- 1 year.
        """

        asset_cycle_phase = space_cycle_phase + (asset_cycle_phase_diff_prop * asset_cycle_period)
        """
        These two cycles are not generally exactly in sync, but they usually are 
        not too far off from each other. 
        """

        return cls.from_params(
            space_cycle_period=space_cycle_period,
            space_cycle_phase=space_cycle_phase,
            space_cycle_amplitude=space_cycle_amplitude,
            space_cycle_asymmetric_parameter=space_cycle_asymmetric_parameter,
            asset_cycle_period=asset_cycle_period,
            asset_cycle_phase=asset_cycle_phase,
            asset_cycle_amplitude=asset_cycle_amplitude,
            asset_cycle_asymmetric_parameter=asset_cycle_asymmetric_parameter,
            sequence=sequence
            )

    @classmethod
    def _from_args(
            cls,
            args: tuple) -> Cyclicality:
        space_cycle_phase_prop, \
            space_cycle_period, \
            space_cycle_height, \
            asset_cycle_period_diff, \
            asset_cycle_phase_diff_prop, \
            asset_cycle_amplitude, \
            space_cycle_asymmetric_param, \
            asset_cycle_asymmetric_param, \
            sequence = args

        return cls.from_estimates(
            space_cycle_phase_prop=space_cycle_phase_prop,
            space_cycle_period=space_cycle_period,
            space_cycle_height=space_cycle_height,
            asset_cycle_period_diff=asset_cycle_period_diff,
            asset_cycle_phase_diff_prop=asset_cycle_phase_diff_prop,
            asset_cycle_amplitude=asset_cycle_amplitude,
            space_cycle_asymmetric_parameter=space_cycle_asymmetric_param,
            asset_cycle_asymmetric_parameter=asset_cycle_asymmetric_param,
            sequence=sequence)

    @classmethod
    def from_likelihoods(
            cls,
            space_cycle_phase_prop_dist: rk.distribution.Form,
            space_cycle_period_dist: rk.distribution.Form,
            space_cycle_height_dist: rk.distribution.Form,
            asset_cycle_phase_diff_prop_dist: rk.distribution.Form,
            asset_cycle_period_diff_dist: rk.distribution.Form,
            asset_cycle_amplitude_dist: rk.distribution.Form,
            space_cycle_asymmetric_parameter_dist: rk.distribution.Form,
            asset_cycle_asymmetric_parameter_dist: rk.distribution.Form,
            sequence: pd.PeriodIndex,
            iterations: int = 1) -> [Cyclicality]:

        space_cycle_phase_props = space_cycle_phase_prop_dist.sample(iterations)
        """
        This distribution should generate the proportion of a full period at 
        which the space cycle starts. If you are unsure completely, then use a 
        uniform distribution from 0 to 1; otherwise use a distribution that 
        reflects your confidence of where the market is in the cycle. 
        """

        space_cycle_periods = space_cycle_period_dist.sample(iterations)
        """
        This distribution should generate the cycle period governing 
        each market simulation (realistically between 10 and 20 years)
        """

        space_cycle_heights = space_cycle_height_dist.sample(iterations)

        asset_cycle_period_diffs = asset_cycle_period_diff_dist.sample(iterations)
        """
        Since the asset cycle period tracks the space cycle period, this 
        distribution should generate reasonable (+/- 1 year) differences
        """

        asset_cycle_phase_props = asset_cycle_phase_diff_prop_dist.sample(iterations)
        """
        The asset market phase is equal to the space market phase +/- some 
        random difference that is a pretty small fraction of the cycle period.
        Reasonably a quarter period. Remember that peak-to-trough is half 
        period, LR mean to either peak or trough is quarter period. 
        """

        asset_cycle_amplitudes = asset_cycle_amplitude_dist.sample(iterations)
        """
        The amplitude of the asset cycle specifies cap rates, which may cycle 
        +/- 100 to 200 basis-points.
        """

        space_cycle_asymmetric_params = space_cycle_asymmetric_parameter_dist.sample(iterations)
        asset_cycle_asymmetric_params = asset_cycle_asymmetric_parameter_dist.sample(iterations)

        args = [
            (space_cycle_phase_prop,
             space_cycle_period,
             space_cycle_height,
             asset_cycle_period_diff,
             asset_cycle_phase_prop,
             asset_cycle_amplitude,
             space_cycle_asymmetric_param,
             asset_cycle_asymmetric_param,
             sequence)
            for (space_cycle_phase_prop,
                 space_cycle_period,
                 space_cycle_height,
                 asset_cycle_period_diff,
                 asset_cycle_phase_prop,
                 asset_cycle_amplitude,
                 space_cycle_asymmetric_param,
                 asset_cycle_asymmetric_param)
            in zip(space_cycle_phase_props,
                   space_cycle_periods,
                   space_cycle_heights,
                   asset_cycle_period_diffs,
                   asset_cycle_phase_props,
                   asset_cycle_amplitudes,
                   space_cycle_asymmetric_params,
                   asset_cycle_asymmetric_params)
            ]

        if iterations == 1:
            return cls._from_args(args[0])
        else:
            pool = multiprocess.Pool(os.cpu_count())
            return pool.map(cls._from_args, args)