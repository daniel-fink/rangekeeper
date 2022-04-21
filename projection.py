from __future__ import annotations
from typing import Optional

import aenum
import numpy as np
import scipy.stats as ss
from abc import ABC, abstractmethod

import distribution


class Extrapolation(ABC):

    @abstractmethod
    def factor(
            self,
            num_periods: int): pass


class LinearExtrapolation(Extrapolation):
    """
    A continuous linearly growing (or decaying) projection from an initial value.
    To calculate the factor, the distribution is initialized with value 1.

    Requires inputs of linear rate of change per period and number of periods.
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
        Returns the multiplicative factor of the distribution's initial value at each period
        """
        return [(self.slope * period_index) for period_index in range(num_periods)]


class UniformExtrapolation(LinearExtrapolation):
    def __init__(self):
        super().__init__(slope=1)


class ExponentialExtrapolation(Extrapolation):
    """
    A continuous exponentially growing (or decaying) distribution between 0 and 1.
    To calculate the density at any point, the distribution is scaled such that the cumulative distribution reaches 1.
    To calculate the factor, the distribution is initialized with value 1.

    Requires inputs of rate of change per period and number of periods.
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
        Returns the multiplicative factor of the distribution's initial value at each period
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
    dist: distribution.Distribution

    def __init__(
            self,
            dist: distribution.Distribution):
        super().__init__()
        self.dist = dist

    def interval_density(
            self,
            parameters: [float]) -> [float]:
        return self.dist.interval_density(parameters)

    def cumulative_density(
            self,
            parameters: [float]) -> [float]:
        return self.dist.cumulative_density(parameters)
