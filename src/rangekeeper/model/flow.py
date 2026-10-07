"""Immutable Flow content and revision-pinned Stream selection.

Movements use date coordinates or period coverage. An optional date on a period
movement is an independent payment/observation fact, not a cached boundary date.
The overall model logic gives quantities their meaning and selects operations.
Flow records do not classify their content as amounts, rates, balances or factors.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from .._schema.records import Flow, Movement, Value
from .._schema.enums import ValueKind
from .._behaviors.flow import MissingValueHandling

if TYPE_CHECKING:
    from .model import Model

__all__ = ["Flow", "Movement", "Stream", "MissingValueHandling"]


@dataclass(frozen=True, slots=True)
class Stream:
    """Ordered selection of canonical Flow Values in one immutable Model revision."""

    model: Model
    value_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        identities = tuple(self.value_ids)
        if len(identities) != len(set(identities)):
            raise ValueError("Stream cannot count the same Value twice")
        for identity in identities:
            value = self.model.value(identity)
            if value.kind is not ValueKind.FLOW:
                raise ValueError(f"Stream target is not a Flow Value: {identity}")
        object.__setattr__(self, "value_ids", identities)

    @classmethod
    def from_values(cls, model: Model, value_ids: Iterable[UUID]) -> Stream:
        """Pin an ordered selection after checking each Value belongs to this revision."""
        return cls(model=model, value_ids=tuple(value_ids))

    @property
    def values(self) -> tuple[Value, ...]:
        """Resolve canonical Values in selection order without duplicating ownership."""
        return tuple(self.model.value(identity) for identity in self.value_ids)

    @property
    def flows(self) -> tuple[Flow, ...]:
        """Read Flow content; unresolved Values cannot supply a calculation input."""
        flows = tuple(value.flow for value in self.values)
        if any(flow is None for flow in flows):
            raise ValueError("Stream contains an unresolved Flow Value")
        return tuple(flow for flow in flows if flow is not None)

    def select(self, *, value_ids: Iterable[UUID]) -> Stream:
        """Return a subset in requested order, retaining the same Model revision."""
        selected = tuple(value_ids)
        if any(identity not in self.value_ids for identity in selected):
            raise KeyError("selection contains a Value outside this Stream")
        return Stream(self.model, selected)

    def merge(self, other: Stream) -> Stream:
        """Union selections in encounter order; different revisions cannot be merged."""
        if self.model.id != other.model.id or self.model._record != other.model._record:
            raise ValueError("Streams must pin the same Model revision and content")
        return Stream(
            self.model, tuple(dict.fromkeys(self.value_ids + other.value_ids))
        )
