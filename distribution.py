from typing import Optional

import aenum
import numpy as np
import scipy.stats as ss


class Distribution:
    class Type(aenum.Enum):

        uniform = 'Uniform distribution', 'Continuous uniform distribution or rectangular distribution'
        linear = 'Linear distribution', 'Linearly increasing or decreasing distribution between minimum and maximum values'
        triangular = 'Triangular distribution', 'Continuous linear distribution with lower limit a, upper limit b and mode c, where a < b and a ≤ c ≤ b.'
        normal = 'Normal distribution', 'Continuous probability distribution defined as the limiting case of a discrete binomial distribution.'
        PERT = 'PERT distribution',

    type: str

    def __init__(
            self,
            generator: Optional[np.random.Generator] = None):
        self.generator = generator
        self.dist = ss.rv_continuous()

    def sample(
            self,
            size: int = 1):
        if self.generator is None:
            generator = np.random.default_rng()
        else:
            generator = self.generator
        variates = self.dist.rvs(size=size, random_state=generator)

        if size == 1:
            return variates[0]
        else:
            return variates


class Symmetric(Distribution):
    def __init__(
            self,
            distribution_type: Distribution.Type,
            mean: float,
            residual: float = 0.,
            generator: Optional[np.random.Generator] = None):
        """
        Parameters that define the mean and residual (maximum deviation)
        of a symmetric distribution
        """
        super().__init__(generator)

        self.mean = mean
        self.residual = residual
        print(distribution_type)
        if distribution_type is Distribution.Type.uniform or distribution_type is Distribution.Type.PERT:
            self.distribution_type = distribution_type
        else:
            raise ValueError("Distribution type must be symmetrical about its mean")
        self.generator = generator

    def distribution(self):
        if self.distribution_type == Distribution.Type.uniform:
            return Uniform(
                lower=self.mean - self.residual,
                range=self.residual * 2,
                generator=self.generator)
        elif self.distribution_type == Distribution.Type.PERT:
            return PERT.standard_symmetric(
                peak=self.mean,
                residual=self.residual)


class Uniform(Distribution):
    """
    For default arguments, this is a continuous, uniform distribution between 0 and 1,
    such the cumulative distribution reaches 1. (For uniform distribution, this means the density is continuously 1).

    For specified arguments, this distribution is constant between lower, and lower + range.
    """

    def __init__(
            self,
            lower: float = 0.,
            range: float = 1.,
            generator: Optional[np.random.Generator] = None):
        super().__init__(generator=generator)
        self.dist = ss.uniform(loc=lower, scale=range)

    def interval_density(
            self,
            parameters: [float]):
        """
        Returns the cumulative density (integral of the distribution curve, or effectively probability)
        between n parameter pairs as intervals (i.e. returns n-1 results)

        :param parameters: Any set of floats between 0 and 1
        :return: List of floats representing the cumulative density of that interval.
        If the input parameters span 0 to 1, the sum of the interval densities will reach 1.
        """

        if (all(parameters) >= 0) & (all(parameters) <= 1):
            return [(self.dist.cdf(parameters[i + 1]) - self.dist.cdf(parameters[i]))
                    for i in (range(0, len(parameters) - 1))]
        else:
            raise ValueError("Error: Parameter must be between 0 and 1 inclusive")

    def cumulative_density(
            self,
            parameters: [float]):
        """
        Returns the cumulative distribution at parameters between 0 and 1.
        """
        if (all(parameters) >= 0) & (all(parameters) <= 1):
            return [self.dist.cdf(parameter) for parameter in parameters]
        else:
            raise ValueError("Error: Parameter must be between 0 and 1 inclusive")


class PERT(Distribution):
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
            generator: Optional[np.random.Generator] = None):
        super().__init__(generator=generator)
        self.peak = peak
        self.weighting = weighting
        self.scale = maximum - minimum
        if (self.weighting >= 0) & (self.peak >= minimum) & (self.peak <= maximum):
            a = (1. + self.weighting * (self.peak - minimum) / (maximum - minimum))
            b = (1. + self.weighting * (maximum - self.peak) / (maximum - minimum))
            self.dist = ss.beta(
                loc=minimum,
                scale=self.scale,
                a=a,
                b=b)
        else:
            raise ValueError("Error: Weighting must be greater than 0 and Peak must be between 0 and 1 inclusive")

    @classmethod
    def standard_symmetric(
            cls,
            peak: float,
            residual: float):
        return cls(
            peak=peak,
            weighting=4.,
            minimum=peak - residual,
            maximum=peak + residual)

    def interval_density(
            self,
            parameters: [float]):
        """
        Returns the cumulative density (integral of the distribution curve, or effectively probability)
        between n parameter pairs as intervals (i.e. returns n-1 results)

        :param parameters: Any set of floats between 0 and 1
        :return: List of floats representing the cumulative density of that interval.
        If the input parameters span 0 to 1, the sum of the interval densities will reach 1.
        """

        if (all(parameters) >= 0) & (all(parameters) <= 1):
            return [(self.dist.cdf(parameters[i + 1]) - self.dist.cdf(parameters[i]))
                    for i in (range(0, len(parameters) - 1))]
        else:
            raise ValueError("Error: Parameter must be between 0 and 1 inclusive")
