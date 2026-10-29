"""Options for Flow and Stream operations, and the aggregate result with coverage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rangekeeper.flow._flow import Flow


@unique
class MissingValueHandling(StrEnum):
    """Treatment of unresolved magnitudes: raise, propagate None, skip or use zero."""

    ERROR = "error"
    PROPAGATE = "propagate"
    SKIP = "skip"
    ZERO = "zero"


@unique
class AlignmentJoin(StrEnum):
    """Select which coordinates an alignment keeps when the Flows differ."""

    EXACT = "exact"
    UNION = "union"
    INTERSECTION = "intersection"


@unique
class AggregationMethod(StrEnum):
    """Select how aligned Flows combine at each coordinate."""

    SUM = "sum"
    MIN = "min"
    MAX = "max"


@unique
class ResampleMethod(StrEnum):
    """Select how movements in one period reduce to one value, or split into shorter ones.

    ``SPLIT`` divides each amount equally over the shorter Periods inside its
    Period; the others reduce the movements inside each longer Period.
    """

    SPLIT = "split"
    SUM = "sum"
    FIRST = "first"
    LAST = "last"
    MEAN = "mean"
    MIN = "min"
    MAX = "max"


@unique
class MeanWeighting(StrEnum):
    """Select the weight of each movement in a resampled mean."""

    OBSERVATIONS = "observations"
    ELAPSED = "elapsed"


@dataclass(frozen=True, slots=True)
class FlowAggregate:
    """A reduced Flow and the known fraction of its inputs at each coordinate."""

    flow: Flow
    coverage: tuple[float, ...]
