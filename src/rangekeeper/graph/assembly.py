from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from .entity import Entity
from .errors import InvalidAssemblyError
from .relationship import Relationship


@dataclass(frozen=True, slots=True, kw_only=True)
class Assembly(Entity):
    """An immutable entity identifying a durable subgraph membership set."""

    entity_ids: frozenset[UUID] = frozenset()
    relationship_ids: frozenset[UUID] = frozenset()

    def __post_init__(self) -> None:
        super(Assembly, self).__post_init__()
        entity_ids = frozenset(self.entity_ids)
        relationship_ids = frozenset(self.relationship_ids)
        if any(not isinstance(item, UUID) for item in entity_ids):
            raise TypeError("entity_ids must contain only UUIDs")
        if any(not isinstance(item, UUID) for item in relationship_ids):
            raise TypeError("relationship_ids must contain only UUIDs")
        if self.id in entity_ids:
            raise InvalidAssemblyError("an assembly cannot contain itself")
        object.__setattr__(self, "entity_ids", entity_ids)
        object.__setattr__(self, "relationship_ids", relationship_ids)

    @classmethod
    def of(
        cls,
        *,
        entities: Iterable[Entity] = (),
        relationships: Iterable[Relationship] = (),
        **values: object,
    ) -> Assembly:
        entity_items = tuple(entities)
        relationship_items = tuple(relationships)
        if any(not isinstance(item, Entity) for item in entity_items):
            raise TypeError("entities must contain only Entity objects")
        if any(not isinstance(item, Relationship) for item in relationship_items):
            raise TypeError("relationships must contain only Relationship objects")
        return cls(
            entity_ids=frozenset(item.id for item in entity_items),
            relationship_ids=frozenset(item.id for item in relationship_items),
            **values,
        )
