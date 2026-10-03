"""Pure finite-quantity reducers; callers explicitly normalize units first."""

import math
from collections.abc import Callable
from ..model import Quantity
from .errors import AggregationError


def _reduce(
    values: tuple[Quantity, ...], operation: Callable[[tuple[float, ...]], float]
) -> Quantity:
    if not values:
        raise AggregationError("cannot reduce an empty population")
    if any(not isinstance(value, Quantity) for value in values):
        raise TypeError("reducers require schema Quantities")
    if any(value.units != values[0].units for value in values):
        raise AggregationError(
            "normalize quantities to identical unit spellings before reduction"
        )
    numbers = tuple(float(value.magnitude) for value in values)
    if not all(math.isfinite(value) for value in numbers):
        raise AggregationError("reducer inputs must be finite")
    try:
        result = operation(numbers)
    except ArithmeticError as error:
        raise AggregationError("quantity reduction overflowed") from error
    if not math.isfinite(result):
        raise AggregationError("quantity reduction produced a non-finite result")
    return Quantity(magnitude=result, units=values[0].units)


def sum_quantities(values: tuple[Quantity, ...]) -> Quantity:
    """Accurately sum normalized magnitudes; empty input is an error, not zero."""
    return _reduce(values, math.fsum)


def mean_quantities(values: tuple[Quantity, ...]) -> Quantity:
    """Average raw contributor quantities, never intermediate subtree averages."""
    return _reduce(
        values, lambda numbers: math.fsum(value / len(numbers) for value in numbers)
    )


def min_quantity(values: tuple[Quantity, ...]) -> Quantity:
    """Return the minimum normalized quantity."""
    return _reduce(values, min)


def max_quantity(values: tuple[Quantity, ...]) -> Quantity:
    """Return the maximum normalized quantity."""
    return _reduce(values, max)


__all__ = ["sum_quantities", "mean_quantities", "min_quantity", "max_quantity"]
