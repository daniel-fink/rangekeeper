from typing import Optional

import enum
import numpy as np
import scipy.stats as ss
from abc import abstractmethod


class Type(enum.Enum):
    UNIFORM = "Uniform"  # Continuous uniform distribution or rectangular distribution
    TRIANGULAR = "Triangular"  # Continuous linear distribution with lower limit a, upper limit b and mode c, where a < b and a ≤ c ≤ b.
    # NORMAL = 'Normal'  # Continuous probability distribution defined as the limiting case of a discrete binomial distribution.
    PERT = "PERT"  # Transformation of the four-parameter Beta distribution defined by the minimum, most likely, and maximum values.


class Form:
    type: Type

    def __init__(self, generator: Optional[np.random.Generator] = None):
        self.generator = generator
        self.dist = ss.rv_continuous()

    def sample(self, size: int = 1):

        if hasattr(self.dist, "b"):
            if self.dist.b == 0.0:
                return (
                    self.dist.a
                )  # If the distribution is a point mass, return the value of the point mass

        if self.generator is None:
            generator = np.random.default_rng()
        else:
            generator = self.generator
        return self.dist.rvs(size=size, random_state=generator)

        # if size == 1:
        #     return variates[0]
        # else:
        #     return variates

    @abstractmethod
    def interval_density(self, parameters: [float]):
        """
        Returns the cumulative density (integral of the interpolated curve)
        between n parameter pairs as intervals (i.e. returns n-1 results)

        :param parameters: Any set of floats between 0 and 1
        :return: List of floats representing the cumulative density of that interval.
        If the input parameters span 0 to 1, the sum of the interval densities will reach 1.
        """

        if (all(parameters) >= 0) & (all(parameters) <= 1):
            return [
                (self.dist.cdf(parameters[i + 1]) - self.dist.cdf(parameters[i]))
                for i in (range(0, len(parameters) - 1))
            ]
        else:
            raise ValueError("Error: Parameter must be between 0 and 1 inclusive")

    @abstractmethod
    def cumulative_density(self, parameters: [float]):
        """
        Returns the cumulative distribution at parameters between 0 and 1.
        """
        if (all(parameters) >= 0) & (all(parameters) <= 1):
            return [self.dist.cdf(parameter) for parameter in parameters]
        else:
            raise ValueError("Error: Parameter must be between 0 and 1 inclusive")


class Symmetric(Form):
    def __init__(
        self,
        type: Type,
        residual: float,
        mean: float = 0,
        generator: Optional[np.random.Generator] = None,
    ):
        """
        Parameters that define the mean and residual (maximum deviation)
        of a symmetric distribution

        :param type: Type of symmetric distribution
        :param residual: Maximum deviation from the mean
        :param mean: Mean of the distribution. Defaults to 0.
        """
        super().__init__(generator=generator)
        if type is Type.UNIFORM or type is Type.PERT or type is Type.TRIANGULAR:
            self.type = type
        else:
            raise ValueError(
                "Distribution type must be able to be symmetrical about its mean"
            )
        self.mean = mean
        self.residual = residual
        self.generator = generator
        self.dist = self._distribution().dist

    def _distribution(self):
        if self.type == Type.UNIFORM:
            return Uniform(
                lower=self.mean - self.residual,
                range=self.residual * 2,
                generator=self.generator,
            )
        elif self.type == Type.PERT:
            return PERT.symmetric(peak=self.mean, residual=self.residual)
        elif self.type == Type.TRIANGULAR:
            return Triangular.symmetric(mode=self.mean, residual=self.residual)

    def interval_density(self, parameters: [float]) -> [float]:
        return self._distribution().interval_density(parameters)

    def cumulative_density(self, parameters: [float]) -> [float]:
        return self._distribution().cumulative_density(parameters)


class Uniform(Form):
    """
    For default arguments, this is a continuous, uniform distribution between 0 and 1,
    such the cumulative distribution reaches 1. (For uniform distribution, this means the density is continuously 1).

    For specified arguments, this distribution is constant between lower, and lower + range.
    """

    def __init__(
        self,
        lower: float = 0.0,
        range: float = 1.0,
        generator: Optional[np.random.Generator] = None,
    ):
        super().__init__(generator=generator)
        self.dist = ss.uniform(loc=lower, scale=range)
        self.type = Type.UNIFORM

    @classmethod
    def symmetric(
        cls,
        mean: float,
        residual: float,
        generator: Optional[np.random.Generator] = None,
    ):
        return cls(lower=mean - residual, range=residual * 2, generator=generator)

    def interval_density(self, parameters: [float]) -> [float]:
        return super().interval_density(parameters)

    def cumulative_density(self, parameters: [float]) -> [float]:
        return super().cumulative_density(parameters)


class Triangular(Form):
    """
    A continuous probability distribution with lower limit a, upper limit b and mode c, where a < b and a ≤ c ≤ b.
    """

    def __init__(
        self,
        lower: float = 0.0,
        upper: float = 1.0,
        mode: float = 0.5,
        generator: Optional[np.random.Generator] = None,
    ):
        super().__init__(generator=generator)
        loc = lower
        scale = upper - lower
        if scale == 0:
            c = lower
        else:
            c = (mode - lower) / (upper - lower)
        self.dist = ss.triang(loc=loc, scale=scale, c=c)
        self.type = Type.TRIANGULAR

    @classmethod
    def symmetric(cls, mode: float, residual: float):
        return cls(lower=mode - residual, upper=mode + residual, mode=mode)

    def interval_density(self, parameters: [float]) -> [float]:
        return super().interval_density(parameters)

    def cumulative_density(self, parameters: [float]) -> [float]:
        return super().cumulative_density(parameters)


class PERT(Form):
    """
    A continuous distribution that is controlled by the placement and weighting of the mode (peak) value.
    It produces similar distributions to the Normal (Gaussian) distribution within a specified domain.
    Its cumulative distribution function (CDF) curve is a classic 's-curve'.

    Peak must be between 0 and 1. Weighting must be >= 0. Standard weighting is 4.

    Specifically, it is a Beta Distribution extended to specified domain,
    with the mean (μ) constrained so that μ = (a + Ɣ*b + c) /  (Ɣ + 2),
    where a and c are the limits (0 and 1 in this formulation), b is the mode (peak value),
    and Ɣ is a weighting factor for the mode.

    This function is built from the formulation in Tensorflow:
    https://github.com/tensorflow/probability/blob/master/tensorflow_probability/python/distributions/pert.py
    """

    def __init__(
        self,
        peak: float = 0.5,
        weighting: float = 4.0,
        minimum: float = 0.0,
        maximum: float = 1.0,
        generator: Optional[np.random.Generator] = None,
    ):
        super().__init__(generator=generator)
        self.type = Type.PERT
        self.peak = peak
        self.weighting = weighting
        self.minimum = minimum
        self.maximum = maximum

        if self.maximum <= self.minimum:
            raise ValueError(
                f"maximum ({self.maximum}) must be greater than minimum ({self.minimum})"
            )

        if not (self.minimum <= self.peak <= self.maximum):
            raise ValueError(
                f"peak must lie between minimum ({self.minimum}) and "
                f"maximum ({self.maximum}), inclusive"
            )

        if self.weighting < 0:
            raise ValueError("weighting must be non-negative (>= 0)")

        # now compute
        self.scale = self.maximum - self.minimum
        a = 1 + self.weighting * (self.peak - self.minimum) / self.scale
        b = 1 + self.weighting * (self.maximum - self.peak) / self.scale

        # finally, instantiate the SciPy beta:
        self.dist = ss.beta(a=a, b=b, loc=self.minimum, scale=self.scale)

    @classmethod
    def symmetric(cls, peak: float, residual: float):
        return cls(
            peak=peak, weighting=4.0, minimum=peak - residual, maximum=peak + residual
        )

    def interval_density(self, parameters: [float]) -> [float]:
        return super().interval_density(parameters)

    def cumulative_density(self, parameters: [float]) -> [float]:
        return super().cumulative_density(parameters)
