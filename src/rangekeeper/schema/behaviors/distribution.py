"""Distribution declarations and calculations with lazy numerical backends."""

from __future__ import annotations
import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, cast
from rangekeeper.schema.enums import DistributionFamily

if TYPE_CHECKING:
    from rangekeeper.schema.records import Distribution, DistributionFamily


class DistributionBehavior:
    """Keep parameter checks, named construction and probability operations together."""

    __slots__ = ()

    def check(self) -> Distribution:
        """Reject invalid support, modes, weights and units; leave the record unchanged."""
        distribution = cast("Distribution", self)
        from rangekeeper.shared.units import default_units

        numbers = [distribution.lower, distribution.upper]
        if distribution.mode is not None:
            numbers.append(distribution.mode)
        if distribution.weighting is not None:
            numbers.append(distribution.weighting)
        if any(not math.isfinite(x) for x in numbers):
            raise ValueError("distribution parameters must be finite")
        if distribution.lower > distribution.upper:
            raise ValueError("invalid distribution bounds")
        if distribution.weighting is not None and distribution.weighting < 0:
            raise ValueError("invalid distribution weighting")
        if distribution.kind is not DistributionFamily.UNIFORM and (
            distribution.mode is None
            or not distribution.lower <= distribution.mode <= distribution.upper
        ):
            raise ValueError("distribution mode outside bounds")
        default_units.validate_units(distribution.units)
        return distribution

    @classmethod
    def uniform(
        cls, *, lower: float = 0, upper: float = 1, units: str = "dimensionless"
    ) -> Distribution:
        """Declare a uniform distribution, including a point mass when bounds coincide."""
        factory = cast("type[Distribution]", cls)

        result = factory(
            kind=DistributionFamily.UNIFORM, lower=lower, upper=upper, units=units
        )
        result.check()
        return result

    @classmethod
    def triangular(
        cls,
        *,
        lower: float = 0,
        upper: float = 1,
        mode: float = 0.5,
        units: str = "dimensionless",
    ) -> Distribution:
        """Declare triangular density with a mode within its closed support."""
        factory = cast("type[Distribution]", cls)

        result = factory(
            kind=DistributionFamily.TRIANGULAR,
            lower=lower,
            upper=upper,
            mode=mode,
            units=units,
        )
        result.check()
        return result

    @classmethod
    def pert(
        cls,
        *,
        lower: float = 0,
        upper: float = 1,
        mode: float = 0.5,
        weighting: float = 4,
        units: str = "dimensionless",
    ) -> Distribution:
        """Declare a PERT distribution with an explicit, nonnegative mode weighting."""
        factory = cast("type[Distribution]", cls)

        result = factory(
            kind=DistributionFamily.PERT,
            lower=lower,
            upper=upper,
            mode=mode,
            weighting=weighting,
            units=units,
        )
        result.check()
        return result

    @classmethod
    def symmetric(
        cls,
        *,
        kind: DistributionFamily,
        mean: float = 0,
        residual: float = 1,
        units: str = "dimensionless",
    ) -> Distribution:
        """Declare support mean ± residual; residual is a half-range, not full width."""
        factory = cast("type[Distribution]", cls)

        if not isinstance(kind, DistributionFamily):
            raise TypeError("kind must be DistributionFamily")
        if not math.isfinite(residual) or residual < 0:
            raise ValueError("residual must be finite and nonnegative")
        if kind is DistributionFamily.UNIFORM:
            return factory.uniform(
                lower=mean - residual, upper=mean + residual, units=units
            )
        if kind is DistributionFamily.TRIANGULAR:
            return factory.triangular(
                lower=mean - residual, upper=mean + residual, mode=mean, units=units
            )
        if kind is DistributionFamily.PERT:
            return factory.pert(
                lower=mean - residual, upper=mean + residual, mode=mean, units=units
            )
        raise ValueError("unsupported distribution")

    def _implementation(self):
        distribution = cast("Distribution", self)
        from scipy import stats

        distribution.check()
        scale = distribution.upper - distribution.lower
        if scale == 0:
            return None
        if distribution.kind is DistributionFamily.UNIFORM:
            return stats.uniform(loc=distribution.lower, scale=scale)
        assert distribution.mode is not None  # Required by the shared semantic check.
        fraction = (distribution.mode - distribution.lower) / scale
        if distribution.kind is DistributionFamily.TRIANGULAR:
            return stats.triang(c=fraction, loc=distribution.lower, scale=scale)
        weighting = 4.0 if distribution.weighting is None else distribution.weighting
        return stats.beta(
            a=1 + weighting * fraction,
            b=1 + weighting * (1 - fraction),
            loc=distribution.lower,
            scale=scale,
        )

    def sample(self, *, size: int, generator) -> tuple[float, ...]:
        """Draw exactly size magnitudes using an explicit NumPy Generator.

        A point mass returns the requested shape without consuming random numbers.
        Negative sizes, wrong generators and invalid distributions raise ValueError.
        The record is immutable; only generator state advances.
        """
        distribution = cast("Distribution", self)
        import numpy as np

        if (
            type(size) is not int
            or size < 0
            or not isinstance(generator, np.random.Generator)
        ):
            raise ValueError(
                "sample requires nonnegative size and an explicit Generator"
            )
        implementation = distribution._implementation()
        if implementation is None:
            return (float(distribution.lower),) * size
        return tuple(
            float(x) for x in implementation.rvs(size=size, random_state=generator)
        )

    def cdf(self, values: Sequence[float]) -> tuple[float, ...]:
        """Evaluate the CDF at finite coordinates in the distribution's declared units."""
        distribution = cast("Distribution", self)
        if any(type(x) not in (float, int) or not math.isfinite(x) for x in values):
            raise ValueError("CDF coordinates must be finite")
        implementation = distribution._implementation()
        if implementation is None:
            return tuple(float(x >= distribution.lower) for x in values)
        return tuple(float(x) for x in implementation.cdf(values))

    def mass(self, boundaries: Sequence[float]) -> tuple[float, ...]:
        """Return masses in ordered intervals, including a point mass at the first bound.

        Require at least two finite, nondecreasing coordinates. No record or random
        state changes; boundaries use the distribution's units.
        """
        distribution = cast("Distribution", self)
        if len(boundaries) < 2 or any(
            b < a for a, b in zip(boundaries, boundaries[1:])
        ):
            raise ValueError(
                "interval boundaries must be ordered and contain at least two values"
            )
        cumulative = distribution.cdf(boundaries)
        result = [b - a for a, b in zip(cumulative, cumulative[1:])]
        if (
            distribution.lower == distribution.upper
            and boundaries[0] == distribution.lower
        ):
            result[0] = 1.0
        return tuple(result)
