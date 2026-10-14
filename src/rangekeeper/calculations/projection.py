"""Known-data paths and allocation, with explicit origin and padding semantics."""

from __future__ import annotations


from collections.abc import Sequence
import math
from enum import Enum, unique
from rangekeeper.model.flux import Flow
from rangekeeper.model.duration import Period
from rangekeeper.model.measure import Quantity
from rangekeeper.model.distribution import Distribution


@unique
class ProjectionMethod(Enum):
    RECURRING = "recurring"
    LINEAR = "linear"
    COMPOUND = "compound"
    DYNAMIC = "dynamic"


@unique
class PaddingMode(Enum):
    NIL = "nil"
    UNITIZE = "unitize"
    EXTEND = "extend"


def project_values(
    initial: float,
    *,
    count: int,
    method: ProjectionMethod = ProjectionMethod.RECURRING,
    rate: float = 0,
    origin: int = 0,
    factors: Sequence[float] | None = None,
) -> tuple[float, ...]:
    """Project known values: linear adds rate per index; compound multiplies (1+rate)^index."""
    if not isinstance(method, ProjectionMethod):
        raise TypeError("method must be a ProjectionMethod")
    if type(count) is not int or count < 0 or type(origin) is not int:
        raise ValueError("count must be nonnegative and origin must be an integer")
    if not math.isfinite(initial) or not math.isfinite(rate):
        raise ValueError("projection inputs must be finite")
    if method == ProjectionMethod.DYNAMIC:
        if factors is None or len(factors) != count:
            raise ValueError("dynamic factors must match the requested length")
        result = tuple(initial * factor for factor in factors)
    elif method == ProjectionMethod.RECURRING:
        result = (float(initial),) * count
    elif method == ProjectionMethod.LINEAR:
        result = tuple(initial + rate * i for i in range(origin, origin + count))
    elif method == ProjectionMethod.COMPOUND:
        result = tuple(initial * (1 + rate) ** i for i in range(origin, origin + count))
    else:
        raise ValueError("unsupported projection method")
    if any(isinstance(value, complex) or not math.isfinite(value) for value in result):
        raise ValueError("projection produced non-finite values")
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


def extrapolate(
    initial: Quantity,
    *,
    periods: Sequence[Period],
    method: ProjectionMethod = ProjectionMethod.RECURRING,
    rate: float = 0,
    origin: int = 0,
    factors: Sequence[float] | None = None,
) -> Flow:
    """Evaluate a known Quantity path over caller-selected periods."""
    return Flow.from_periods(
        periods,
        project_values(
            initial.magnitude,
            count=len(periods),
            method=method,
            rate=rate,
            origin=origin,
            factors=factors,
        ),
        units=initial.units,
    )


def distribute(
    quantity: Quantity,
    *,
    periods: Sequence[Period],
    distribution: Distribution | None = None,
    weights: Sequence[float] | None = None,
) -> Flow:
    """Distribute a total without changing mass; explicit weights must sum to one.

    A distribution allocates equal increments of its support, not equal durations.
    Supply explicit duration weights when allocation should follow elapsed time.
    """
    if not periods or weights is not None and distribution is not None:
        raise ValueError("allocation needs periods and at most one weight source")
    if weights is None:
        distribution = distribution or Distribution.uniform()
        bounds = [
            distribution.lower
            + (distribution.upper - distribution.lower) * i / len(periods)
            for i in range(len(periods) + 1)
        ]
        if distribution.lower == distribution.upper:
            weights = (1.0,) + (0.0,) * (len(periods) - 1)
        else:
            weights = distribution.mass(bounds)
    if (
        len(weights) != len(periods)
        or any(not math.isfinite(w) or w < 0 for w in weights)
        or not math.isclose(math.fsum(weights), 1, abs_tol=1e-12)
    ):
        raise ValueError(
            "allocation weights must be finite, nonnegative and sum to one"
        )
    values = [quantity.magnitude * w for w in weights]
    # Assign roundoff to the final bucket so total content retains the stated amount.
    values[-1] += quantity.magnitude - math.fsum(values)
    return Flow.from_periods(periods, values, units=quantity.units)
