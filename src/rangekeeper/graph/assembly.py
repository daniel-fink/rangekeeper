from __future__ import annotations

from collections.abc import Iterable

from .characteristics import Characteristics
from .classification import Classification
from .entity import Entity
from .errors import InvalidAssemblyError
from .provenance import Provenance
from .relationship import Relationship


class Assembly(Entity):
    """An identifiable, durable subgraph made from domain object references."""

    __slots__ = ("_entities", "_relationships")

    def __init__(
        self,
        entity_id: str | None = None,
        name: str | None = None,
        classification: Classification | None = None,
        characteristics: Characteristics | None = None,
        provenance: Provenance | None = None,
        *,
        entities: Iterable[Entity] = (),
        relationships: Iterable[Relationship] = (),
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            name=name,
            classification=classification,
            characteristics=characteristics,
            provenance=provenance,
        )
        self._entities: set[Entity] = set()
        self._relationships: set[Relationship] = set()
        self._replace_contents(entities=entities, relationships=relationships)

    @property
    def entities(self) -> frozenset[Entity]:
        return frozenset(self._entities)

    @property
    def relationships(self) -> frozenset[Relationship]:
        return frozenset(self._relationships)

    def _replace_contents(
        self,
        *,
        entities: Iterable[Entity],
        relationships: Iterable[Relationship],
    ) -> None:
        """Validate and atomically replace contents for the future Graph boundary."""
        prepared_entities, prepared_relationships = self._prepare_contents(
            entities=entities,
            relationships=relationships,
        )
        self._entities = prepared_entities
        self._relationships = prepared_relationships

    def _prepare_contents(
        self,
        *,
        entities: Iterable[Entity],
        relationships: Iterable[Relationship],
    ) -> tuple[set[Entity], set[Relationship]]:
        """Validate proposed contents without mutating the Assembly."""
        materialized_entities = list(entities)
        materialized_relationships = list(relationships)
        entity_by_id = self._index_unique_entities(materialized_entities)
        relationship_by_id = self._index_unique_relationships(
            materialized_relationships
        )

        if self.entity_id in entity_by_id:
            raise InvalidAssemblyError("an assembly cannot contain itself")
        self._validate_no_recursive_containment(entity_by_id.values())

        allowed_endpoint_ids = {self.entity_id, *entity_by_id}
        for relationship in relationship_by_id.values():
            if relationship.source_id not in allowed_endpoint_ids:
                raise InvalidAssemblyError(
                    f"relationship {relationship.relationship_id!r} source endpoint "
                    f"{relationship.source_id!r} is not contained by the assembly"
                )
            if relationship.target_id not in allowed_endpoint_ids:
                raise InvalidAssemblyError(
                    f"relationship {relationship.relationship_id!r} target endpoint "
                    f"{relationship.target_id!r} is not contained by the assembly"
                )

        return set(entity_by_id.values()), set(relationship_by_id.values())

    @staticmethod
    def _index_unique_entities(entities: Iterable[Entity]) -> dict[str, Entity]:
        by_id: dict[str, Entity] = {}
        for entity in entities:
            if not isinstance(entity, Entity):
                raise TypeError("assembly entities must be Entity instances")
            existing = by_id.get(entity.entity_id)
            if existing is not None and existing is not entity:
                raise InvalidAssemblyError(
                    f"different Entity objects share entity_id {entity.entity_id!r}"
                )
            by_id[entity.entity_id] = entity
        return by_id

    @staticmethod
    def _index_unique_relationships(
        relationships: Iterable[Relationship],
    ) -> dict[str, Relationship]:
        by_id: dict[str, Relationship] = {}
        for relationship in relationships:
            if not isinstance(relationship, Relationship):
                raise TypeError("assembly relationships must be Relationship instances")
            existing = by_id.get(relationship.relationship_id)
            if existing is not None and existing is not relationship:
                raise InvalidAssemblyError(
                    "different Relationship objects share relationship_id "
                    f"{relationship.relationship_id!r}"
                )
            by_id[relationship.relationship_id] = relationship
        return by_id

    def _validate_no_recursive_containment(self, entities: Iterable[Entity]) -> None:
        pending = [entity for entity in entities if isinstance(entity, Assembly)]
        visited: set[str] = set()
        while pending:
            assembly = pending.pop()
            if assembly.entity_id == self.entity_id:
                raise InvalidAssemblyError("assembly containment would create a cycle")
            if assembly.entity_id in visited:
                continue
            visited.add(assembly.entity_id)
            pending.extend(
                entity for entity in assembly._entities if isinstance(entity, Assembly)
            )
