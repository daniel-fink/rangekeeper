from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Generic, TypeVar
from uuid import UUID

from .entity import Entity

if TYPE_CHECKING:
    from .view import View


T = TypeVar("T")

__all__ = ["Aggregation"]


@dataclass(frozen=True, slots=True)
class Aggregation(Generic[T]):
    """Immutable per-entity values aggregated over one hierarchical View."""

    view: View
    _values: Mapping[UUID, T | None] = field(repr=False)

    def __post_init__(self) -> None:
        values = dict(self._values)
        if set(values) != {entity.id for entity in self.view.entities}:
            raise ValueError("aggregation values must match the View entities")
        object.__setattr__(self, "_values", MappingProxyType(values))

    @property
    def root_value(self) -> T | None:
        return self._values[self.view.roots[0].id]

    def __getitem__(self, entity: str | UUID | Entity) -> T | None:
        identifier = self.view._resolve_view_entity_id(entity)
        return self._values[identifier]

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[Entity]:
        return iter(self.view.entities)

    def items(self) -> tuple[tuple[Entity, T | None], ...]:
        return tuple((entity, self._values[entity.id]) for entity in self)
