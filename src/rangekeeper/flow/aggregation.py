"""The result of an aggregation of Flows, with its coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rangekeeper.flow.flow import Flow

__all__ = ["FlowAggregate"]


@dataclass(frozen=True, slots=True)
class FlowAggregate:
    """A reduced Flow and the known fraction of its inputs at each coordinate."""

    flow: Flow
    coverage: tuple[float, ...]
