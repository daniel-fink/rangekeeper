"""Schema-owned probability distributions and pure named constructors.

Bounds, modes and returned samples have the declared units. Construction does not
sample, calculate paths or import a numerical backend. Model validation and the
calculation functions use the same semantic checks.
"""

import math
from .._schema.records import Distribution, DistributionFamily
from ..units import default_units

__all__ = [
    "Distribution",
    "make_uniform",
    "make_triangular",
    "make_pert",
    "make_symmetric",
    "validate_distribution",
]


def validate_distribution(distribution: Distribution) -> None:
    """Reject invalid support, modes, weights and units; leave the record unchanged."""
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
    if distribution.kind != "uniform" and (
        distribution.mode is None
        or not distribution.lower <= distribution.mode <= distribution.upper
    ):
        raise ValueError("distribution mode outside bounds")
    default_units.compatible(distribution.units, distribution.units)


def make_uniform(
    *, lower: float = 0, upper: float = 1, units: str = "dimensionless"
) -> Distribution:
    """Declare a uniform distribution, including a point mass when bounds coincide."""
    result = Distribution(kind="uniform", lower=lower, upper=upper, units=units)
    validate_distribution(result)
    return result


def make_triangular(
    *,
    lower: float = 0,
    upper: float = 1,
    mode: float = 0.5,
    units: str = "dimensionless"
) -> Distribution:
    """Declare triangular density with a mode within its closed support."""
    result = Distribution(
        kind="triangular", lower=lower, upper=upper, mode=mode, units=units
    )
    validate_distribution(result)
    return result


def make_pert(
    *,
    lower: float = 0,
    upper: float = 1,
    mode: float = 0.5,
    weighting: float = 4,
    units: str = "dimensionless"
) -> Distribution:
    """Declare a PERT distribution with an explicit, nonnegative mode weighting."""
    result = Distribution(
        kind="pert",
        lower=lower,
        upper=upper,
        mode=mode,
        weighting=weighting,
        units=units,
    )
    validate_distribution(result)
    return result


def make_symmetric(
    *,
    kind: DistributionFamily,
    mean: float = 0,
    residual: float = 1,
    units: str = "dimensionless"
) -> Distribution:
    """Declare support mean ± residual; residual is a half-range, not full width."""
    if not math.isfinite(residual) or residual < 0:
        raise ValueError("residual must be finite and nonnegative")
    if kind == "uniform":
        return make_uniform(lower=mean - residual, upper=mean + residual, units=units)
    if kind == "triangular":
        return make_triangular(
            lower=mean - residual, upper=mean + residual, mode=mean, units=units
        )
    if kind == "pert":
        return make_pert(
            lower=mean - residual, upper=mean + residual, mode=mean, units=units
        )
    raise ValueError("unsupported distribution")
