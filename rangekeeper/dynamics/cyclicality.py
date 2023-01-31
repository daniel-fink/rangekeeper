import math

import numpy as np
import pandas as pd
from numba import jit

from .. import distribution, flux, measure


class Enumerate:
    @staticmethod
    @jit(nopython=True)
    def sine(
            period: float,
            span: float,
            amplitude: float,
            num_periods: int):
        """
        Generate a sine wave from the parameters.
        The conventional, symmetric cycle is a simple sine function, parameterized:
        y = amplitude * sin((t - span) * (2 * pi / period))
        """
        data = []
        for i in range(num_periods):
            data.append(amplitude *
                        np.sin(
                            (i - span) *
                            (2 * np.pi / period)
                            )
                        )
        return data

    @staticmethod
    def asymmetric_sine(
            period: float,
            span: float,
            amplitude: float,
            parameter: float,
            num_periods: int,
            precision: float = 1e-10,
            bound: float = 1e-1):
        """
        Generate a smoothed sinusoid asymmetric (sawtooth) wave.
        Based on the solution to the expression: f(x) = sin(x - f(x)),
        with additional parameterization of period, span, amplitude, and shear,
        where shear is defined as a parameter between 0 and 1 (1 being most asymmetric)

        Because the formula is recursive, we approximate the solution by
        solving sin(x + c) - x = 0, for x, as in this answer https://math.stackexchange.com/a/2645080
        to https://math.stackexchange.com/q/2644982/999815
        """

        @jit(nopython=True)
        def f(x):
            upper = 1 + bound
            lower = -upper
            while upper - lower > precision:
                mid = (lower + upper) / 2
                if -math.sin((x - span) * (2 * np.pi / period) + mid) - ((1 / parameter) * mid) > 0:
                    lower = mid
                else:
                    upper = mid
            return (lower + upper) / 2 * (amplitude * (1 / -parameter))

        return list(map(f, range(num_periods)))


class Cycle:
    def __init__(
            self,
            period: float,
            span: float,
            amplitude: float):
        """
        Parameters that define a cyclical time series
        """
        self.period = period
        self.span = span
        self.amplitude = amplitude

    def __str__(self):
        string = ""
        string += "Period: " + str(self.period) + "\n"
        string += "Span: " + str(self.span) + "\n"
        string += "Amplitude: " + str(self.amplitude) + "\n"
        return string

    def sine(
            self,
            index: pd.PeriodIndex,
            name: str = "sine_cycle"):
        data = Enumerate.sine(
            period=self.period,
            span=self.span,
            amplitude=self.amplitude,
            num_periods=index.size)
        return flux.Flow(
            movements=pd.Series(data=data, index=index),
            units=measure.scalar,
            name=name)

    def asymmetric_sine(
            self,
            parameter: float,
            index: pd.PeriodIndex,
            precision: float = 1e-10,
            bound: float = 1e-1,
            name: str = "asymmetric_sine_cycle") -> flux.Flow:
        data = Enumerate.asymmetric_sine(
            period=self.period,
            span=self.span,
            amplitude=self.amplitude,
            parameter=parameter,
            num_periods=index.size,
            precision=precision,
            bound=bound)
        return flux.Flow(
            movements=pd.Series(
                data=data,
                index=index),
            # units=measure.scalar,
            name=name)


class Cyclicality:
    def __init__(
            self,
            params: dict,
            index: pd.PeriodIndex):
        """
        This models a (possibly somewhat) predictable long-term cycle in the
        pricing. In fact, there are two cycles, not necessarily in sync,
        one for the space market (rents) and another separate cycle for the
        asset market (capital flows), the latter reflected by the cap rate.

        Cycles are modeled by generalized sine functions governed by the given
        input period, amplitude, and span.

        """
        space_period = distribution.Symmetric(
            mean=params['space_cycle_period_mean'],
            residual=params['space_cycle_period_residual'],
            distribution_type=params['space_cycle_period_dist']
            ).distribution().sample()
        """
        In the U.S. the real estate market cycle seems to be in the range of 10 to 20 years. 
        E.g.:
        =RAND()*10+10
        This will randomly generate the cycle period governing each
        future history to be between 10 and 20 years.
        """

        space_span = distribution.Symmetric(
            mean=params['space_cycle_span_offset'],
            residual=params['space_cycle_span_residual'],
            distribution_type=params['space_cycle_span_dist']
            ).distribution().sample() * space_period
        """
        If you make this equal to a uniform RV times the rent cycle period 
        then the span will range from starting anywhere from peak to trough with equal likelihood.
        E.g.:
        =RAND()*J10, if the Period is in J10.
        
        If you think you know where you are in the cycle, 
        then use this relationship of Span to Cycle Period:
        Span=:             Cycle:
        (1/4)Period   = Bottom of cycle, headed up.
        (1/2)Period   = Mid-cycle, headed down.
        (3/4)Period   = Top of cycle, headed down.
        (1/1)Period   = Mid-cycle, headed up.
        
        Example, if you enter 20 in cycle period, and you enter 5 in cycle span, 
        then the cycle will be starting out in the first year at the bottom of the cycle, 
        heading up from there.

        NOTE: FOLLOWING IS TO BE UPDATED WITH NEW SAWTOOTH ALGO:
        TODO: FIX.
                
        Please note that with the compound-sine asymetric cycle formula, 
        the peak parameter is slightly off from the above. 
        0.65*Period seems to start the cycle closer to the peak. 
        For example, if you want the span to vary randomly and 
        uniformly over the 1/8 of the cycle that is the top of the upswing (late boom just before downturn),
        you would enter:
        =(.175*RAND()+.65)*J10, if Period is in J10.
        """
        space_amplitude = distribution.Symmetric(
            mean=params['space_cycle_amplitude_mean'],
            residual=params['space_cycle_amplitude_residual'],
            distribution_type=params['space_cycle_amplitude_dist']
            ).distribution().sample()

        self.space_cycle = Cycle(
            period=space_period,
            span=space_span,
            amplitude=space_amplitude)

        asset_period = distribution.Symmetric(
            mean=params['asset_cycle_period_offset'],
            residual=params['asset_cycle_period_residual'],
            distribution_type=params['asset_cycle_period_dist']
            ).distribution().sample() + space_period
        """
        This  can be randomly different from rent cycle period, 
        but probably not too different, maybe +/- 1 year.
        E.g.:
        =J10+(RAND()*2-1)
        """

        asset_span = distribution.Symmetric(
            mean=params['asset_cycle_span_offset'],
            residual=params['asset_cycle_span_residual'],
            distribution_type=params['asset_cycle_span_dist']
            ).distribution().sample() * asset_period + space_span
        """
        Since we input this cycle as the negative of the actual cap rate cycle, 
        you can think of the span in the same way as the space market span. 
        These two cycles are not generally exactly in sync, but the usually are not too far off.
        Hence, probably makes sense to set this asset market span 
        equal to the space market span +/- some random difference 
        that is a pretty small fraction of the cycle period. 
        Remember that peak-to-trough is half period, LR mean to either peak or trough is quarter period. 
        E.g.: =J8+(RAND()*J11/5-J11/10)
        Above would let asset span differ from space span by +/- a bit less than a quarter-period 
        (here, a fifth of the asset cycle period).
        """

        asset_amplitude = distribution.Symmetric(
            mean=params['asset_cycle_amplitude_mean'],
            residual=params['asset_cycle_amplitude_residual'],
            distribution_type=params['asset_cycle_amplitude_dist']
            ).distribution().sample()
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

        self.asset_cycle = Cycle(
            period=asset_period,
            span=asset_span,
            amplitude=asset_amplitude)

        space_waveform = self.space_cycle.asymmetric_sine(
            index=index,
            name='space_waveform',
            parameter=params['space_cycle_asymmetric_parameter'])
        self.space_waveform = flux.Flow(
            name=space_waveform.name,
            movements=(1 + space_waveform.movements),
            units=space_waveform.units)
        """
        This models a (possibly somewhat) predictable long-term cycle in the 
        pricing. In fact, there are two cycles, not necessarily in sync, one
        for the space market (rents) and another separate cycle for the asset 
        market (capital flows), the latter reflected by the cap rate. 
        We model each separately, the space market cycle in this column and 
        the asset market cycle in a column to the right. Cycles are modeled 
        by generalized sine functions governed by the given input period, 
        amplitude, and span.
        """

        self.asset_waveform = self.asset_cycle.asymmetric_sine(
            index=index,
            name='asset_waveform',
            parameter=params['asset_cycle_asymmetric_parameter'])
        """
        Negative of actual cap rate cycle. This makes this cycle directly
        reflect the asset pricing, as prices are an inverse function of the 
        cap rate. By taking the negative of the actual cap rate, we therefore 
        make it easier to envision the effect on prices.
        """
