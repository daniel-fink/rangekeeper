from typing import Optional

import aenum
import numpy as np
import scipy.stats as ss
from abc import ABC, abstractmethod

import distribution


class Extrapolation(ABC):
    class Type:
        _init_ = 'value', '__doc__'

        exponential = 'Exponential extrapolation', 'Constant-rate growth or decay from an initial value'
        linear = 'Linear extrapolation', 'Straight-line projection from an initial value'

    type: str

    @abstractmethod
    def factor(
            self,
            num_periods: int): pass


class Linear(Extrapolation):
    """
    A continuous linearly growing (or decaying) projection from an initial value.
    To calculate the factor, the distribution is initialized with value 1.

    Requires inputs of linear rate of change per period and number of periods.
    """

    def __init__(
            self,
            slope: float):
        self.slope = slope

    def factor(
            self,
            num_periods: int) -> [float]:
        """
        Returns the multiplicative factor of the distribution's initial value at each period
        """
        return [(self.slope * period_index) for period_index in range(num_periods)]


class Uniform(Linear):
    def __init__(self):
        super().__init__(slope=1)


class Exponential(Extrapolation):
    """
    A continuous exponentially growing (or decaying) distribution between 0 and 1.
    To calculate the density at any point, the distribution is scaled such that the cumulative distribution reaches 1.
    To calculate the factor, the distribution is initialized with value 1.

    Requires inputs of rate of change per period and number of periods.
    """

    def __init__(
            self,
            rate: float):
        self.rate = rate

    def factor(
            self,
            num_periods: int) -> [float]:
        """
        Returns the multiplicative factor of the distribution's initial value at each period
        """
        return [np.power((1 + self.rate), period_index) for period_index in range(num_periods)]


class Interpolation(ABC):
    class Type:
        _init_ = 'value', '__doc__'

        distributive = 'Distributive interpolation', "Apportionment of a total value according to the density function of a probability distribution"
        linear = 'Linear interpolation', 'Weighted-average approximation between given values'
        polynomial = 'Polynomial interpolation', ''

    type: str


class Distribution(Interpolation):
    dist: distribution.Distribution

    def __init__(
            self,
            dist: distribution.Distribution):
        self.dist = dist

    def interval_density(
            self,
            parameters: [float]) -> [float]:
        return self.dist.interval_density(parameters)

    def cumulative_density(
            self,
            parameters: [float]) -> [float]:
        return self.dist.cumulative_density(parameters)
