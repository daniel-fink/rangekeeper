"""Profiles: how an amount develops over Periods.

A growth profile (``Constant``, ``Linear``, ``Compounding``) gives a multiple
of an initial amount for each Period. The amount grows from ``base``, the
date of the initial amount; it is zero before ``start``; and with ``every``
it occurs once in each such length of time from ``start``. A distribution
profile (``Uniform``, ``SCurve``) gives each Period's share of a total, over
the Periods from ``start`` for a ``length`` of time.
``rangekeeper.flow.Flow.from_profile`` makes the Flow, with ``initial=`` for
a growth profile and ``total=`` for a distribution profile. Profiles register
in ``profiles`` (ADR-013).
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum, unique
from itertools import pairwise
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Protocol, runtime_checkable

from rangekeeper.duration import NEVER, DateValue, Period
from rangekeeper.duration.calendar import offset, require_date
from rangekeeper.duration.dates import require_date_value
from rangekeeper.duration.errors import AlignmentError
from rangekeeper.duration.period import steps
from rangekeeper.quantity import Quantity, default_units
from rangekeeper.schema import records
from rangekeeper.schema.enums import DistributionFamily
from rangekeeper.schema.kinds import register
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError
from rangekeeper.shared.optional import requires
from rangekeeper.shared.registry import Registry

if TYPE_CHECKING:
    import numpy

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
    a share of the total. The shares of a distribution profile add up to one,
    or are all zero when the profile places no share, as with a ``start`` of
    ``NEVER``.
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
    value = default_units.convert(quantity=quantity, to="pa").number
    if not math.isfinite(value) or value <= -1:
        raise ContractError(
            "a growth rate must be greater than -100 % pa",
            values={"rate": f"{quantity.magnitude} {quantity.units}"},
        )
    return value


def _base(base: date | None) -> date | None:
    """Require the date of the initial amount, when one is given."""
    return None if base is None else require_date(base)


def _start(start: DateValue | None) -> DateValue | None:
    """Require a date value, or NEVER, for the first date of a profile."""
    return None if start is None else require_date_value(start)


def _length(length: Quantity | str | None, *, name: str) -> Quantity | None:
    """Return a positive whole length, such as ``"5 years"``, as a Quantity."""
    if length is None:
        return None
    quantity = Quantity(text=length) if isinstance(length, str) else length
    if not isinstance(quantity, records.Quantity):
        raise TypeError(f"{name} must be a Quantity or its text, such as '5 years'")
    steps(quantity)  # Raises UnitError for a length that is not whole steps.
    return Quantity(magnitude=quantity.magnitude, units=quantity.units)


def _require_periods(periods: Sequence[Period]) -> None:
    """Require at least one Period for a distribution."""
    if not periods:
        raise ContractError(
            "a distribution needs at least one Period", values={"periods": 0}
        )


def _elapsed_years(origin: date, day: date) -> float:
    """Return the years from ``origin`` to ``day``.

    A day on the same day of the month as the origin counts whole months, so
    twelve months are one year. Other days count days, at 365.25 days a year.
    """
    if day.day == origin.day:
        return ((day.year - origin.year) * 12 + day.month - origin.month) / 12
    return (day - origin).days / 365.25


def _years(periods: Sequence[Period], *, base: date | None) -> tuple[float, ...]:
    """Return the years from ``base``, or the first Period, to the start of each."""
    if not periods:
        return ()
    origin = periods[0].start if base is None else base
    return tuple(_elapsed_years(origin, period.start) for period in periods)


def _occurrences(
    periods: Sequence[Period], *, start: DateValue | None, every: Quantity | None
) -> tuple[int, ...]:
    """Return how many times a growth profile's amount occurs in each Period.

    Without ``every``, the amount occurs once in each Period that does not
    end on or before ``start``. With ``every``, it occurs on ``start`` (by
    default the start of the first Period) and once each ``every`` after it,
    in the Period that contains each date. ``NEVER`` gives no occurrence.
    """
    if start is NEVER or not periods:
        return (0,) * len(periods)
    if every is None:
        return tuple(
            0 if start is not None and period.end <= start else 1 for period in periods
        )
    anchor = periods[0].start if start is None else start
    assert isinstance(anchor, date)
    return _repeats(periods, anchor=anchor, every=every)


def _repeats(
    periods: Sequence[Period], *, anchor: date, every: Quantity
) -> tuple[int, ...]:
    """Return how many of the dates ``anchor + k * every`` fall in each Period."""
    frequency, count = steps(every)
    counts = [0] * len(periods)
    starts = [period.start for period in periods]
    step = 0
    while (day := offset(value=anchor, frequency=frequency, count=step * count)) < (
        periods[-1].end
    ):
        index = bisect_right(starts, day) - 1
        if index >= 0 and day < periods[index].end:
            counts[index] += 1
        step += 1
    return tuple(counts)


def _growth(
    periods: Sequence[Period],
    *,
    start: DateValue | None,
    every: Quantity | None,
    factors: Sequence[float],
) -> tuple[float, ...]:
    """Return each Period's growth factor times the occurrences in it."""
    counts = _occurrences(periods, start=start, every=every)
    return tuple(n * factor for n, factor in zip(counts, factors, strict=True))


def _window(
    periods: Sequence[Period], *, start: DateValue | None, length: Quantity | None
) -> range:
    """Return the indices of the Periods inside ``[start, start + length)``.

    The window starts at ``start``, by default the start of the first Period,
    and ends ``length`` later, by default at the end of the last Period. It
    must lie inside the Periods and cover whole Periods; otherwise
    AlignmentError. A ``start`` of ``NEVER`` gives no Period.
    """
    if start is NEVER:
        return range(0)
    first = periods[0].start if start is None else start
    assert isinstance(first, date)
    if length is None:
        end = periods[-1].end
    else:
        frequency, count = steps(length)
        end = offset(value=first, frequency=frequency, count=count)
    window = Period(start=first, end=end)
    _require_inside(periods, window=window)
    inside = [
        i for i, p in enumerate(periods) if p.start < window.end and p.end > first
    ]
    for i in inside:
        if periods[i].start < first or periods[i].end > window.end:
            raise AlignmentError(
                f"the profile window {_interval(window)} crosses the Period "
                f"{_interval(periods[i])}; choose whole Periods",
                code=Code.ALIGNMENT_CROSSES,
                values={"window": _interval(window), "period": _interval(periods[i])},
            )
    return range(inside[0], inside[-1] + 1) if inside else range(0)


def _require_inside(periods: Sequence[Period], *, window: Period) -> None:
    """Require a profile window inside the Periods, so no share is lost."""
    covered = Period(start=periods[0].start, end=periods[-1].end)
    if window.start < covered.start or window.end > covered.end:
        raise AlignmentError(
            f"the profile window {_interval(window)} runs past the Periods "
            f"{_interval(covered)}; give Periods that cover it",
            code=Code.ALIGNMENT_PARTIAL,
            values={"window": _interval(window), "periods": _interval(covered)},
        )


def _interval(period: Period) -> str:
    """Return a Period as an ISO 8601 interval, such as ``2026-01-01/2027-01-01``."""
    return f"{period.start.isoformat()}/{period.end.isoformat()}"


def _shares(
    periods: Sequence[Period], *, window: range, shares: Sequence[float]
) -> tuple[float, ...]:
    """Return the shares on the Periods of the window, and zero elsewhere."""
    result = [0.0] * len(periods)
    for index, share in zip(window, shares, strict=True):
        result[index] = share
    return tuple(result)


@dataclass(frozen=True, slots=True, kw_only=True, init=False)
class Constant:
    """Growth profile: the initial amount in every Period.

    ``start`` gives zero before a date: each Period that ends on or before it
    holds zero, and the Period that contains it holds the amount. ``every``
    gives the amount once in each length of time from ``start``, such as
    ``"5 years"``, in the Period that contains each date; without ``start``,
    from the start of the first Period. A ``start`` of ``NEVER`` gives zero.
    """

    start: DateValue | None
    every: Quantity | None
    takes: ClassVar[Literal["initial", "total"]] = "initial"

    def __init__(
        self,
        *,
        start: DateValue | None = None,
        every: Quantity | str | None = None,
    ) -> None:
        object.__setattr__(self, "start", _start(start))
        object.__setattr__(self, "every", _length(every, name="every"))

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return one for each occurrence of the amount in each Period."""
        return _growth(
            periods,
            start=self.start,
            every=self.every,
            factors=(1.0,) * len(periods),
        )


@dataclass(frozen=True, slots=True, kw_only=True, init=False)
class Linear:
    """Growth profile: the initial amount grows by ``rate`` of itself each year.

    The factor of a Period that starts ``t`` years after ``base`` is
    ``1 + rate * t``. ``base`` is the date of the initial amount, by default
    the start of the first Period. ``start`` and ``every`` are those of
    ``Constant``.
    """

    rate: float
    base: date | None
    start: DateValue | None
    every: Quantity | None
    takes: ClassVar[Literal["initial", "total"]] = "initial"

    def __init__(
        self,
        *,
        rate: Quantity | str,
        base: date | None = None,
        start: DateValue | None = None,
        every: Quantity | str | None = None,
    ) -> None:
        object.__setattr__(self, "rate", _rate(rate))
        object.__setattr__(self, "base", _base(base))
        object.__setattr__(self, "start", _start(start))
        object.__setattr__(self, "every", _length(every, name="every"))

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return ``1 + rate * t`` for each occurrence of the amount in each Period."""
        return _growth(
            periods,
            start=self.start,
            every=self.every,
            factors=[1 + self.rate * t for t in _years(periods, base=self.base)],
        )


@dataclass(frozen=True, slots=True, kw_only=True, init=False)
class Compounding:
    """Growth profile: the initial amount compounds at ``rate`` per year.

    The factor of a Period that starts ``t`` years after ``base`` is
    ``(1 + rate) ** t``, so yearly Periods at ``"2 % pa"`` give 1, 1.02,
    1.0404 and so on. ``base`` is the date of the initial amount, by default
    the start of the first Period. ``start`` and ``every`` are those of
    ``Constant``: ``Compounding(rate="3 % pa", start=opening)`` grows on one
    calendar from the first Period, and is zero before the opening.
    """

    rate: float
    base: date | None
    start: DateValue | None
    every: Quantity | None
    takes: ClassVar[Literal["initial", "total"]] = "initial"

    def __init__(
        self,
        *,
        rate: Quantity | str,
        base: date | None = None,
        start: DateValue | None = None,
        every: Quantity | str | None = None,
    ) -> None:
        object.__setattr__(self, "rate", _rate(rate))
        object.__setattr__(self, "base", _base(base))
        object.__setattr__(self, "start", _start(start))
        object.__setattr__(self, "every", _length(every, name="every"))

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return ``(1 + rate) ** t`` for each occurrence of the amount in each Period."""
        return _growth(
            periods,
            start=self.start,
            every=self.every,
            factors=[(1 + self.rate) ** t for t in _years(periods, base=self.base)],
        )


@dataclass(frozen=True, slots=True, kw_only=True, init=False)
class Uniform:
    """Distribution profile: an equal share of the total in each Period.

    ``start`` and ``length`` give the window of the shares, such as
    ``Uniform(start=date(2028, 1, 1), length="2 years")``; the Periods
    outside it hold zero. By default the window starts with the first Period
    and ends with the last. The window must cover whole Periods inside the
    Periods; otherwise AlignmentError. A ``start`` of ``NEVER`` gives zero
    shares, because the payments do not happen.
    """

    start: DateValue | None
    length: Quantity | None
    takes: ClassVar[Literal["initial", "total"]] = "total"

    def __init__(
        self,
        *,
        start: DateValue | None = None,
        length: Quantity | str | None = None,
    ) -> None:
        object.__setattr__(self, "start", _start(start))
        object.__setattr__(self, "length", _length(length, name="length"))

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return ``1 / n`` for each of the ``n`` Periods of the window."""
        _require_periods(periods)
        window = _window(periods, start=self.start, length=self.length)
        shares = (1 / len(window),) * len(window) if window else ()
        return _shares(periods, window=window, shares=shares)


@dataclass(frozen=True, slots=True, kw_only=True, init=False)
class SCurve:
    """Distribution profile: shares that rise, then fall, along an S-shaped total.

    Each Period's share is the increase of a cumulative distribution over its
    equal part of the Periods. The default is ``3x² - 2x³``, the cumulative
    distribution of Beta(2, 2). ``distribution`` gives another one, such as
    ``rangekeeper.model.Distribution.pert()``, in units of the fraction of the
    Periods. ``start`` and ``length`` give the window of the shares, as for
    ``Uniform``.
    """

    distribution: Distribution | None
    start: DateValue | None
    length: Quantity | None
    takes: ClassVar[Literal["initial", "total"]] = "total"

    def __init__(
        self,
        *,
        distribution: Distribution | None = None,
        start: DateValue | None = None,
        length: Quantity | str | None = None,
    ) -> None:
        object.__setattr__(self, "distribution", distribution)
        object.__setattr__(self, "start", _start(start))
        object.__setattr__(self, "length", _length(length, name="length"))

    def factors(self, *, periods: Sequence[Period]) -> tuple[float, ...]:
        """Return the increase of the cumulative distribution over each Period."""
        _require_periods(periods)
        window = _window(periods, start=self.start, length=self.length)
        shares = self._curve(len(window)) if window else ()
        return _shares(periods, window=window, shares=shares)

    def _curve(self, count: int) -> tuple[float, ...]:
        """Return the shares of ``count`` equal parts of the S-curve."""
        bounds = [i / count for i in range(count + 1)]
        if self.distribution is None:
            cumulative = [x * x * (3 - 2 * x) for x in bounds]
            return tuple(b - a for a, b in pairwise(cumulative))
        low, high = self.distribution.lower, self.distribution.upper
        if low == high:
            return (1.0,) + (0.0,) * (count - 1)
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
    profiles.register(name=_name, implementation=_profile)


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

    def _implementation(self) -> Any:
        """Return the frozen SciPy distribution, or None for a point mass."""
        distribution = self
        with requires("calculations"):
            from scipy import stats  # noqa: PLC0415 - optional dependency

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

    def sample(
        self, *, size: int, generator: numpy.random.Generator
    ) -> tuple[float, ...]:
        """Draw exactly size magnitudes using an explicit NumPy Generator.

        A point mass returns the requested shape without consuming random numbers.
        Negative sizes, wrong generators and invalid distributions raise ValueError.
        The record is immutable; only generator state advances.
        """
        distribution = self
        with requires("calculations"):
            import numpy as np  # noqa: PLC0415 - optional dependency

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

    def fill(
        mode: PaddingMode, count: int, endpoint: float | None
    ) -> tuple[float, ...]:
        if not count:
            return ()
        if mode is PaddingMode.EXTEND:
            if endpoint is None:
                raise ValueError("cannot extend an empty path")
            return (endpoint,) * count
        return ({PaddingMode.NIL: 0.0, PaddingMode.UNITIZE: 1.0}[mode],) * count

    return (
        fill(left, before, values[0] if values else None)
        + tuple(values)
        + fill(right, after, values[-1] if values else None)
    )
