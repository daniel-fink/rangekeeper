"""Calculations on the shared Distribution record; no second parameter schema.

Sampling advances only the caller's generator. Returned magnitudes use the
record's units; probabilities and interval masses are dimensionless. SciPy and
NumPy load only when a calculation needs them.
"""

import math
from collections.abc import Sequence
from ..model.distribution import Distribution, validate_distribution


def _implementation(distribution: Distribution):
    from scipy import stats

    validate_distribution(distribution)
    scale = distribution.upper - distribution.lower
    if scale == 0:
        return None
    if distribution.kind == "uniform":
        return stats.uniform(loc=distribution.lower, scale=scale)
    assert distribution.mode is not None  # Required by the shared semantic check.
    fraction = (distribution.mode - distribution.lower) / scale
    if distribution.kind == "triangular":
        return stats.triang(c=fraction, loc=distribution.lower, scale=scale)
    weighting = 4.0 if distribution.weighting is None else distribution.weighting
    return stats.beta(
        a=1 + weighting * fraction,
        b=1 + weighting * (1 - fraction),
        loc=distribution.lower,
        scale=scale,
    )


def sample(distribution: Distribution, *, size: int, generator) -> tuple[float, ...]:
    """Draw exactly size magnitudes using an explicit NumPy Generator.

    A point mass returns the requested shape without consuming random numbers.
    Negative sizes, wrong generators and invalid distributions raise ValueError.
    The record is immutable; only generator state advances.
    """
    import numpy as np

    if (
        type(size) is not int
        or size < 0
        or not isinstance(generator, np.random.Generator)
    ):
        raise ValueError("sample requires nonnegative size and an explicit Generator")
    implementation = _implementation(distribution)
    if implementation is None:
        return (float(distribution.lower),) * size
    return tuple(
        float(x) for x in implementation.rvs(size=size, random_state=generator)
    )


def calculate_cumulative_density(
    distribution: Distribution, values: Sequence[float]
) -> tuple[float, ...]:
    """Evaluate the CDF at finite coordinates in the distribution's declared units."""
    if any(type(x) not in (float, int) or not math.isfinite(x) for x in values):
        raise ValueError("CDF coordinates must be finite")
    implementation = _implementation(distribution)
    if implementation is None:
        return tuple(float(x >= distribution.lower) for x in values)
    return tuple(float(x) for x in implementation.cdf(values))


def calculate_interval_mass(
    distribution: Distribution, boundaries: Sequence[float]
) -> tuple[float, ...]:
    """Return masses in ordered intervals, including a point mass at the first bound.

    Require at least two finite, nondecreasing coordinates. No record or random
    state changes; boundaries use the distribution's units.
    """
    if len(boundaries) < 2 or any(b < a for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError(
            "interval boundaries must be ordered and contain at least two values"
        )
    cumulative = calculate_cumulative_density(distribution, boundaries)
    result = [b - a for a, b in zip(cumulative, cumulative[1:])]
    if distribution.lower == distribution.upper and boundaries[0] == distribution.lower:
        result[0] = 1.0
    return tuple(result)
