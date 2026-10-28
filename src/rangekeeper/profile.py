"""Profiles: how an amount develops over Periods.

A growth profile (``Constant``, ``Linear``, ``Compounding``) gives a multiple
of an initial amount for each Period; the first Period holds the initial
amount. A distribution profile (``Uniform``, ``SCurve``) gives each Period's
share of a total. ``rangekeeper.flow.Flow.from_profile`` makes the Flow, with
``initial=`` for a growth profile and ``total=`` for a distribution profile.
Profiles register in ``profiles`` (ADR-013).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, unique
from itertools import pairwise
from typing import ClassVar, Literal, Protocol, runtime_checkable

from rangekeeper.duration import Period
from rangekeeper.quantity import Quantity, default_units
from rangekeeper.schema import records
from rangekeeper.schema.enums import DistributionFamily
from rangekeeper.schema.kinds import register
from rangekeeper.shared.optional import requires
from rangekeeper.shared.registry import Registry

# Distribution is public as rangekeeper.model.Distribution (one public path).
__all__ = [
    "Compounding",
    "Constant",
    "Linear",
    "Profile",
    "SCurve",
    "Uniform",
    "profiles",
]


@runtime_checkable
class Profile(Protocol):
    """How an amount develops over Periods.

    ``takes`` names the amount that the profile needs: ``"initial"`` for a
    growth profile, ``"total"`` for a distribution profile. ``factors``
    returns one number for each Period: a multiple of the initial amount, or
    a share of the total. The shares of a distribution profile add up to one.
    """

    takes: ClassVar[Literal["initial", "total"]]

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return one factor for each Period."""
        ...


def _rate(rate: Quantity | str) -> float:
    """Return a rate per year, such as ``"2 % pa"``, as a number per year."""
    quantity = Quantity(text=rate) if isinstance(rate, str) else rate
    if not isinstance(quantity, records.Quantity):
        raise TypeError("rate must be a Quantity or its text, such as '2 % pa'")
    value = default_units.convert(quantity, to="pa").number
    if not math.isfinite(value) or value <= -1:
        raise ValueError("a growth rate must be greater than -100 % pa")
    return value


def _years(periods: Sequence[Period]) -> tuple[float, ...]:
    """Return the years from the start of the first Period to the start of each.

    A start on the same day of the month as the first counts whole months, so
    twelve months are one year. Other starts count days, at 365.25 days a year.
    """
    if not periods:
        return ()
    first = periods[0].start
    return tuple(
        ((p.start.year - first.year) * 12 + p.start.month - first.month) / 12
        if p.start.day == first.day
        else (p.start - first).days / 365.25
        for p in periods
    )


@dataclass(frozen=True, slots=True)
class Constant:
    """Growth profile: the initial amount in every Period."""

    takes: ClassVar[Literal["initial", "total"]] = "initial"

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return one for each Period."""
        return (1.0,) * len(periods)


@dataclass(frozen=True, slots=True, init=False)
class Linear:
    """Growth profile: the initial amount grows by ``rate`` of itself each year.

    The factor of a Period that starts ``t`` years after the first is
    ``1 + rate * t``.
    """

    rate: float
    takes: ClassVar[Literal["initial", "total"]] = "initial"

    def __init__(self, *, rate: Quantity | str) -> None:
        object.__setattr__(self, "rate", _rate(rate))

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return ``1 + rate * t`` for each Period."""
        return tuple(1 + self.rate * t for t in _years(periods))


@dataclass(frozen=True, slots=True, init=False)
class Compounding:
    """Growth profile: the initial amount compounds at ``rate`` per year.

    The factor of a Period that starts ``t`` years after the first is
    ``(1 + rate) ** t``, so yearly Periods at ``"2 % pa"`` give 1, 1.02,
    1.0404 and so on.
    """

    rate: float
    takes: ClassVar[Literal["initial", "total"]] = "initial"

    def __init__(self, *, rate: Quantity | str) -> None:
        object.__setattr__(self, "rate", _rate(rate))

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return ``(1 + rate) ** t`` for each Period."""
        return tuple((1 + self.rate) ** t for t in _years(periods))


@dataclass(frozen=True, slots=True)
class Uniform:
    """Distribution profile: an equal share of the total in each Period."""

    takes: ClassVar[Literal["initial", "total"]] = "total"

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return ``1 / n`` for each of ``n`` Periods."""
        if not periods:
            raise ValueError("a distribution needs at least one Period")
        return (1 / len(periods),) * len(periods)


@dataclass(frozen=True, slots=True)
class SCurve:
    """Distribution profile: shares that rise, then fall, along an S-shaped total.

    Each Period's share is the increase of a cumulative distribution over its
    equal part of the Periods. The default is ``3x² - 2x³``, the cumulative
    distribution of Beta(2, 2). ``distribution`` gives another one, such as
    ``rangekeeper.model.Distribution.pert()``, in units of the fraction of the
    Periods.
    """

    distribution: Distribution | None = None
    takes: ClassVar[Literal["initial", "total"]] = "total"

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return the increase of the cumulative distribution over each Period."""
        if not periods:
            raise ValueError("a distribution needs at least one Period")
        bounds = [i / len(periods) for i in range(len(periods) + 1)]
        if self.distribution is None:
            cumulative = [x * x * (3 - 2 * x) for x in bounds]
            return tuple(b - a for a, b in pairwise(cumulative))
        low, high = self.distribution.lower, self.distribution.upper
        if low == high:
            return (1.0,) + (0.0,) * (len(periods) - 1)
        return self.distribution.mass([low + (high - low) * x for x in bounds])


# Profiles by name, for equation text and extensions (ADR-013). Each name holds
# a profile class; an installed distribution can add one in the entry point
# group ``rangekeeper.profiles``.
profiles: Registry[type] = Registry("profiles", type)
for _name, _profile in (
    ("constant", Constant),
    ("linear", Linear),
    ("compounding", Compounding),
    ("uniform", Uniform),
    ("scurve", SCurve),
):
    profiles.register(_name, _profile)


@register
class Distribution(records.Distribution):
    """Keep parameter checks, named construction and probability operations together."""

    __slots__ = ()

    def _invariants(self) -> None:
        """Reject non-finite parameters, invalid bounds, weights and modes."""
        numbers = [self.lower, self.upper]
        if self.mode is not None:
            numbers.append(self.mode)
        if self.weighting is not None:
            numbers.append(self.weighting)
        if any(not math.isfinite(x) for x in numbers):
            raise ValueError("distribution parameters must be finite")
        if self.lower > self.upper:
            raise ValueError("invalid distribution bounds")
        if self.weighting is not None and self.weighting < 0:
            raise ValueError("invalid distribution weighting")
        if self.kind is not DistributionFamily.UNIFORM and (
            self.mode is None or not self.lower <= self.mode <= self.upper
        ):
            raise ValueError("distribution mode outside bounds")

    def check(self) -> Distribution:
        """Check the units against the default unit system; return this record.

        The parameter rules hold from construction.
        """
        from rangekeeper.quantity import default_units

        default_units.validate_units(self.units)
        return self

    @classmethod
    def uniform(
        cls, *, lower: float = 0, upper: float = 1, units: str = "dimensionless"
    ) -> Distribution:
        """Declare a uniform distribution, including a point mass when bounds coincide."""
        factory = cls

        result = factory(
            kind=DistributionFamily.UNIFORM, lower=lower, upper=upper, units=units
        )
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
        factory = cls

        result = factory(
            kind=DistributionFamily.TRIANGULAR,
            lower=lower,
            upper=upper,
            mode=mode,
            units=units,
        )
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
        factory = cls

        result = factory(
            kind=DistributionFamily.PERT,
            lower=lower,
            upper=upper,
            mode=mode,
            weighting=weighting,
            units=units,
        )
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
        factory = cls

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
        distribution = self
        with requires("calculations"):
            from scipy import stats

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
        distribution = self
        with requires("calculations"):
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
        distribution = self
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
        distribution = self
        if len(boundaries) < 2 or any(b < a for a, b in pairwise(boundaries)):
            raise ValueError(
                "interval boundaries must be ordered and contain at least two values"
            )
        cumulative = distribution.cdf(boundaries)
        result = [b - a for a, b in pairwise(cumulative)]
        if (
            distribution.lower == distribution.upper
            and boundaries[0] == distribution.lower
        ):
            result[0] = 1.0
        return tuple(result)


@unique
class GrowthMethod(Enum):
    """Select how a growth profile grows the initial value at each index."""

    RECURRING = "recurring"
    LINEAR = "linear"
    COMPOUND = "compound"
    DYNAMIC = "dynamic"


@unique
class PaddingMode(Enum):
    """Select the value that fills padded rows: zero, one or the nearest endpoint."""

    NIL = "nil"
    UNITIZE = "unitize"
    EXTEND = "extend"


def grow_values(
    initial: float,
    *,
    count: int,
    method: GrowthMethod = GrowthMethod.RECURRING,
    rate: float = 0,
    origin: int = 0,
    factors: Sequence[float] | None = None,
) -> tuple[float, ...]:
    """Grow known values: linear adds rate per index; compound multiplies (1+rate)^index."""
    if not isinstance(method, GrowthMethod):
        raise TypeError("method must be a GrowthMethod")
    if type(count) is not int or count < 0 or type(origin) is not int:
        raise ValueError("count must be nonnegative and origin must be an integer")
    if not math.isfinite(initial) or not math.isfinite(rate):
        raise ValueError("growth inputs must be finite")
    if method == GrowthMethod.DYNAMIC:
        if factors is None or len(factors) != count:
            raise ValueError("dynamic factors must match the requested length")
        result = tuple(initial * factor for factor in factors)
    elif method == GrowthMethod.RECURRING:
        result = (float(initial),) * count
    elif method == GrowthMethod.LINEAR:
        result = tuple(initial + rate * i for i in range(origin, origin + count))
    elif method == GrowthMethod.COMPOUND:
        result = tuple(initial * (1 + rate) ** i for i in range(origin, origin + count))
    else:
        raise ValueError("unsupported growth method")
    if any(isinstance(value, complex) or not math.isfinite(value) for value in result):
        raise ValueError("growth produced non-finite values")
    return result


def pad(
    values: Sequence[float],
    *,
    before: int = 0,
    after: int = 0,
    left: PaddingMode = PaddingMode.NIL,
    right: PaddingMode = PaddingMode.NIL,
) -> tuple[float, ...]:
    """Add exactly the requested rows: nil=0, unitize=1, extend=nearest endpoint."""
    if not isinstance(left, PaddingMode) or not isinstance(right, PaddingMode):
        raise TypeError("padding modes must be PaddingMode members")
    if any(type(n) is not int or n < 0 for n in (before, after)):
        raise ValueError("padding lengths must be nonnegative integers")

    def fill(mode, count, endpoint):
        if count and mode == PaddingMode.EXTEND and endpoint is None:
            raise ValueError("cannot extend an empty path")
        return (
            {
                PaddingMode.NIL: 0.0,
                PaddingMode.UNITIZE: 1.0,
                PaddingMode.EXTEND: endpoint,
            }[mode],
        ) * count

    return (
        fill(left, before, values[0] if values else None)
        + tuple(values)
        + fill(right, after, values[-1] if values else None)
    )
