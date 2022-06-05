from __future__ import annotations
from typing import Optional

import aenum
import numpy as np
import scipy.stats as ss
from abc import ABC, abstractmethod

try:
    import distribution
except:
    import modules.rangekeeper.distribution as distribution


class Extrapolation(ABC):
    @abstractmethod
    def factor(
            self,
            num_periods: int): pass


class LinearExtrapolation(Extrapolation):
    """
    A linearly growing (or decaying) projection from an initial value.
    To calculate the factor, the projection is modelled as a linear function of (slope * period) + 1
    """

    def __init__(
            self,
            slope: float):
        super().__init__()
        self.slope = slope

    def factor(
            self,
            num_periods: int) -> [float]:
        """
        Returns the multiplicative factor of the projection at each period
        """
        return [(self.slope * period_index) + 1 for period_index in range(num_periods)]


class UniformExtrapolation(LinearExtrapolation):
    def __init__(self):
        super().__init__(slope=0)


class ExponentialExtrapolation(Extrapolation):
    """
    An exponentially growing (compounding) or decaying projection at a specified rate per period.
    To calculate the factor, the projection is modelled as an exponential function of (1 + rate) ** period
    """

    def __init__(
            self,
            rate: float):
        super().__init__()
        self.rate = rate

    def factor(
            self,
            num_periods: int) -> [float]:
        """
        Returns the multiplicative factor of the projection at each period
        """
        return [np.power((1 + self.rate), period_index) for period_index in range(num_periods)]


class Interpolation(ABC):
    def interval_density(
            self,
            parameters: [float]) -> [float]:
        pass

    def cumulative_density(
            self,
            parameters: [float]) -> [float]:
        pass


class DistributiveInterpolation(Interpolation):
    """
    A projection that apportions values over a range, according to a specified
    distribution type.
    """
    dist: distribution.Distribution

    def __init__(
            self,
            dist: distribution.Distribution):
        super().__init__()
        self.dist = dist

    def interval_density(
            self,
            parameters: [float]) -> [float]:
        """
        Returns the cumulative density (integral of the interpolated curve)
        between n parameter pairs as intervals (i.e. returns n-1 results)

        :param parameters: Any set of floats between 0 and 1
        :return: List of floats representing the cumulative density of that interval.
        If the input parameters span 0 to 1, the sum of the interval densities will reach 1.
        """
        return self.dist.interval_density(parameters)

    def cumulative_density(
            self,
            parameters: [float]) -> [float]:
        """
        Returns the cumulative distribution at any parameter between 0 and 1.
        """
        return self.dist.cumulative_density(parameters)
