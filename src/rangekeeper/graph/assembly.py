from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID, uuid4

from .characteristics import Characteristics
from .classification import Classification
from .entity import Entity
from .errors import InvalidAssemblyError
from .relationship import Relationship


__all__ = ["Assembly"]


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
        id: UUID | None = None,
        code: str | None = None,
        name: str | None = None,
        classification: Classification | None = None,
        characteristics: Characteristics | None = None,
    ) -> Assembly:
        """Create an assembly from objects while retaining only stable membership IDs."""

        entity_items = tuple(entities)
        relationship_items = tuple(relationships)
        if any(not isinstance(item, Entity) for item in entity_items):
            raise TypeError("entities must contain only Entity objects")
        if any(not isinstance(item, Relationship) for item in relationship_items):
            raise TypeError("relationships must contain only Relationship objects")
        return cls(
            id=uuid4() if id is None else id,
            code=code,
            name=name,
            classification=classification,
            characteristics=(
                Characteristics() if characteristics is None else characteristics
            ),
            entity_ids=frozenset(item.id for item in entity_items),
            relationship_ids=frozenset(item.id for item in relationship_items),
        )
