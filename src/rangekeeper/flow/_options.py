"""Options for Flow and Stream operations, and the aggregate result with coverage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rangekeeper.schema.records import Flow


@unique
class AlignmentJoin(Enum):
    """Select which coordinates an alignment keeps when the Flows differ."""

    EXACT = "exact"
    UNION = "union"
    INTERSECTION = "intersection"


@unique
class AggregationMethod(Enum):
    """Select how aligned Flows combine at each coordinate."""

    SUM = "sum"
    MIN = "min"
    MAX = "max"


@unique
class ResamplingMethod(Enum):
    """Select how movements in one period reduce to one value."""

    SUM = "sum"
    FIRST = "first"
    LAST = "last"
    MEAN = "mean"
    MIN = "min"
    MAX = "max"


@unique
class MeanWeighting(Enum):
    """Select the weight of each movement in a resampled mean."""

    OBSERVATIONS = "observations"
    ELAPSED = "elapsed"


@dataclass(frozen=True, slots=True)
class FlowAggregate:
    """A reduced Flow and the known fraction of its inputs at each coordinate."""

    flow: Flow
    coverage: tuple[float, ...]
