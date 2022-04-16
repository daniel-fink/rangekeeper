from typing import Optional

import aenum
import numpy as np
import scipy.stats as ss


class Extrapolation:
    class Type:
        _init_ = 'value', '__doc__'

        exponential = 'Exponential extrapolation', 'Constant-rate growth or decay from an initial value'
        linear = 'Linear extrapolation', 'Straight-line projection from an initial value'

    type: str


class Linear(Extrapolation):
    """
    A continuous linearly growing (or decaying) projection from an initial value.
    To calculate the factor, the distribution is initialized with value 1.

    Requires inputs of linear rate of change per period and number of periods.
    """

    def __init__(
            self,
            slope: float,
            num_periods: int):
        self.slope = slope
        self.num_periods = num_periods

    def factor(self):
        """
        Returns the multiplicative factor of the distribution's initial value at each period
        """
        return [(self.slope * period_index) for period_index in range(self.num_periods)]


class Exponential(Extrapolation):
    """
    A continuous exponentially growing (or decaying) distribution between 0 and 1.
    To calculate the density at any point, the distribution is scaled such that the cumulative distribution reaches 1.
    To calculate the factor, the distribution is initialized with value 1.

    Requires inputs of rate of change per period and number of periods.
    """

    def __init__(
            self,
            rate: float,
            num_periods: int):
        self.rate = rate
        self.num_periods = num_periods

    def factor(self):
        """
        Returns the multiplicative factor of the distribution's initial value at each period
        """
        return [np.power((1 + self.rate), period_index) for period_index in range(self.num_periods)]
