"""Immutable distribution parameters with caller-owned random generators.

These are calculation objects, not persistent domain records. A point mass always
returns the requested sample shape. CDF arguments are support coordinates; interval
mass checks every boundary and never mistakes ``all(values)`` for a range check.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class Distribution:
    kind: str
    lower: float
    upper: float
    mode: float | None = None
    weighting: float = 4.0

    def __post_init__(self):
        if self.kind not in {"uniform", "triangular", "pert"}:
            raise ValueError("unsupported distribution")
        parameters = [self.lower, self.upper, self.weighting]
        if self.mode is not None:
            parameters.append(self.mode)
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in parameters):
            raise ValueError("distribution parameters must be finite numbers")
        if self.lower > self.upper or self.weighting < 0:
            raise ValueError("invalid distribution bounds/weighting")
        if self.kind != "uniform" and (
            self.mode is None or not self.lower <= self.mode <= self.upper
        ):
            raise ValueError("mode must lie within distribution bounds")

    def _implementation(self):
        from scipy import stats

        scale = self.upper - self.lower
        if scale == 0:
            return None
        if self.kind == "uniform":
            return stats.uniform(loc=self.lower, scale=scale)
        fraction = (self.mode - self.lower) / scale
        if self.kind == "triangular":
            return stats.triang(c=fraction, loc=self.lower, scale=scale)
        return stats.beta(
            a=1 + self.weighting * fraction,
            b=1 + self.weighting * (1 - fraction),
            loc=self.lower,
            scale=scale,
        )

    def sample(self, *, size: int, generator) -> tuple[float, ...]:
        """Draw from an explicit numpy Generator; always return exactly size samples."""
        import numpy as np

        if (
            type(size) is not int
            or size < 0
            or not isinstance(generator, np.random.Generator)
        ):
            raise ValueError(
                "sample requires nonnegative size and an explicit Generator"
            )
        implementation = self._implementation()
        if implementation is None:
            return (float(self.lower),) * size
        return tuple(
            float(x) for x in implementation.rvs(size=size, random_state=generator)
        )

    def cumulative_density(self, values: Sequence[float]) -> tuple[float, ...]:
        if any(type(x) not in (float, int) or not math.isfinite(x) for x in values):
            raise ValueError("CDF coordinates must be finite")
        implementation = self._implementation()
        if implementation is None:
            return tuple(float(x >= self.lower) for x in values)
        return tuple(float(x) for x in implementation.cdf(values))

    def interval_mass(self, boundaries: Sequence[float]) -> tuple[float, ...]:
        """Return mass in successive intervals; include a point mass at the first bound."""
        if len(boundaries) < 2 or any(
            b < a for a, b in zip(boundaries, boundaries[1:])
        ):
            raise ValueError(
                "interval boundaries must be ordered and contain at least two values"
            )
        cumulative = self.cumulative_density(boundaries)
        result = [b - a for a, b in zip(cumulative, cumulative[1:])]
        if self.lower == self.upper and boundaries[0] == self.lower:
            result[0] = 1.0
        return tuple(result)

    @classmethod
    def uniform(cls, *, lower: float = 0, upper: float = 1) -> Distribution:
        return cls("uniform", lower, upper)

    @classmethod
    def triangular(
        cls, *, lower: float = 0, upper: float = 1, mode: float = 0.5
    ) -> Distribution:
        return cls("triangular", lower, upper, mode)

    @classmethod
    def pert(
        cls,
        *,
        lower: float = 0,
        upper: float = 1,
        mode: float = 0.5,
        weighting: float = 4,
    ) -> Distribution:
        return cls("pert", lower, upper, mode, weighting)

    @classmethod
    def symmetric(
        cls, *, kind: str, mean: float = 0, residual: float = 1
    ) -> Distribution:
        if residual < 0:
            raise ValueError("residual must be nonnegative")
        return cls(
            kind, mean - residual, mean + residual, mean if kind != "uniform" else None
        )
