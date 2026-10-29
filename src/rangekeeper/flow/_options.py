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
    """Select how the movements inside one target Period reduce to one amount.

    ``MEAN`` gives each movement the same weight. ``ELAPSED_MEAN`` weights each
    movement by the days that its Period covers, so it needs period movements.
    To divide amounts over shorter Periods, use ``Flow.split``.
    """

    SUM = "sum"
    FIRST = "first"
    LAST = "last"
    MEAN = "mean"
    ELAPSED_MEAN = "elapsed_mean"
    MIN = "min"
    MAX = "max"


@dataclass(frozen=True, slots=True)
class FlowAggregate:
    """A reduced Flow and the known fraction of its inputs at each coordinate."""

    flow: Flow
    coverage: tuple[float, ...]
