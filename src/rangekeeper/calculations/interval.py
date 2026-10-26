"""Pure interval partitioning; persistent membership belongs to the Model graph."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True, slots=True)
class Interval:
    """A range of real numbers between finite ordered bounds."""

    left: float
    right: float

    def __post_init__(self):
        if (
            not math.isfinite(self.left)
            or not math.isfinite(self.right)
            or self.left > self.right
        ):
            raise ValueError("interval requires finite ordered bounds")

    @property
    def length(self) -> float:
        """Return the distance from the left bound to the right bound."""
        return self.right - self.left

    def split(self, proportion: float) -> tuple["Interval", "Interval"]:
        """Split into two Intervals; the left one takes the given proportion."""
        if not 0 < proportion < 1:
            raise ValueError("split proportion must lie strictly between zero and one")
        left, right = self.subdivide((proportion, 1 - proportion))
        return left, right

    def subdivide(self, divisions: int | Sequence[float]) -> tuple["Interval", ...]:
        """Partition into equal pieces or explicit positive fractions summing to one."""
        if isinstance(divisions, bool):
            raise TypeError("division count must not be boolean")
        if isinstance(divisions, int):
            if divisions <= 0:
                raise ValueError("division count must be positive")
            fractions = (1 / divisions,) * divisions
        else:
            fractions = tuple(divisions)
        if (
            not fractions
            or any(not math.isfinite(x) or x <= 0 for x in fractions)
            or not math.isclose(math.fsum(fractions), 1, abs_tol=1e-12)
        ):
            raise ValueError("fractions must be positive and sum to one")
        points = (
            [self.left]
            + [
                self.left + self.length * math.fsum(fractions[:i])
                for i in range(1, len(fractions))
            ]
            + [self.right]
        )
        return tuple(Interval(a, b) for a, b in pairwise(points))
