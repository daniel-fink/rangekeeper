"""Known-data paths and allocation, with explicit origin and padding semantics."""

from __future__ import annotations

from collections.abc import Sequence
import math
from ..model.flow import Flow, from_periods
from ..model.duration import Period
from ..model.measure import Quantity
from .distribution import Distribution


def project_values(
    initial: float,
    *,
    count: int,
    method: str = "recurring",
    rate: float = 0,
    origin: int = 0,
    factors: Sequence[float] | None = None,
) -> tuple[float, ...]:
    """Project known values: linear adds rate per index; compound multiplies (1+rate)^index."""
    if type(count) is not int or count < 0 or type(origin) is not int:
        raise ValueError("count must be nonnegative and origin must be an integer")
    if not math.isfinite(initial) or not math.isfinite(rate):
        raise ValueError("projection inputs must be finite")
    if method == "dynamic":
        if factors is None or len(factors) != count:
            raise ValueError("dynamic factors must match the requested length")
        result = tuple(initial * factor for factor in factors)
    elif method == "recurring":
        result = (float(initial),) * count
    elif method == "linear":
        result = tuple(initial + rate * i for i in range(origin, origin + count))
    elif method == "compound":
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
    left: str = "nil",
    right: str = "nil",
) -> tuple[float, ...]:
    """Add exactly the requested rows: nil=0, unitize=1, extend=nearest endpoint."""
    if any(type(n) is not int or n < 0 for n in (before, after)):
        raise ValueError("padding lengths must be nonnegative integers")

    def fill(mode, count, endpoint):
        if mode not in {"nil", "unitize", "extend"}:
            raise ValueError("unknown padding mode")
        if count and mode == "extend" and endpoint is None:
            raise ValueError("cannot extend an empty path")
        return ({"nil": 0.0, "unitize": 1.0, "extend": endpoint}[mode],) * count

    return (
        fill(left, before, values[0] if values else None)
        + tuple(values)
        + fill(right, after, values[-1] if values else None)
    )


def project(
    initial: Quantity,
    *,
    periods: Sequence[Period],
    method: str = "recurring",
    rate: float = 0,
    origin: int = 0,
    factors: Sequence[float] | None = None,
) -> Flow:
    """Evaluate a known Quantity path over caller-selected periods."""
    return from_periods(
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


def allocate(
    quantity: Quantity,
    *,
    periods: Sequence[Period],
    distribution: Distribution | None = None,
    weights: Sequence[float] | None = None,
) -> Flow:
    """Allocate a total without changing mass; explicit weights must already sum to one.

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
            weights = distribution.interval_mass(bounds)
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
    return from_periods(periods, values, units=quantity.units)
