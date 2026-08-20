from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from .assembly import Assembly
from .characteristics import Characteristics
from .classification import Classification
from .entity import Entity
from .provenance import Provenance
from .relationship import Relationship
from .taxonomy import Taxonomy


if TYPE_CHECKING:
    from .model import Model


AssemblyMember = Entity | Relationship


class EntityRegistry:
    """Model-bound registration, lookup, and traversal for entities."""

    __slots__ = ("_model",)

    def __init__(self, model: Model) -> None:
        self._model = model

    def add(self, entity: Entity) -> Entity:
        return self._model._add_entities((entity,))[0]

    def add_all(self, entities: Iterable[Entity]) -> tuple[Entity, ...]:
        return self._model._add_entities(entities)

    def __getitem__(self, entity_id: str) -> Entity:
        return self._model._entity(entity_id)

    def get(self, entity_id: str) -> Entity | None:
        if not isinstance(entity_id, str):
            raise TypeError("entity_id must be a string")
        return self._model._entities.get(entity_id)

    def all(self) -> tuple[Entity, ...]:
        return tuple(self._model._entities.values())

    def predecessors(
        self,
        entity: Entity | str,
        relationship: Classification | str | None = None,
    ) -> tuple[Entity, ...]:
        canonical = self._model._resolve_entity(entity)
        return self._model._predecessors(
            canonical.entity_id,
            relationship,
            entity_ids=frozenset(self._model._entities),
            relationship_ids=frozenset(self._model._relationships),
        )

    def successors(
        self,
        entity: Entity | str,
        relationship: Classification | str | None = None,
    ) -> tuple[Entity, ...]:
        canonical = self._model._resolve_entity(entity)
        return self._model._successors(
            canonical.entity_id,
            relationship,
            entity_ids=frozenset(self._model._entities),
            relationship_ids=frozenset(self._model._relationships),
        )


class RelationshipRegistry:
    """Model-bound registration, creation, and lookup for relationships."""

    __slots__ = ("_model",)

    def __init__(self, model: Model) -> None:
        self._model = model

    def add(self, relationship: Relationship) -> Relationship:
        return self._model._add_relationships((relationship,))[0]

    def add_all(
        self,
        relationships: Iterable[Relationship],
    ) -> tuple[Relationship, ...]:
        return self._model._add_relationships(relationships)

    def connect(
        self,
        source: Entity | str,
        target: Entity | str,
        classification: Classification,
        *,
        characteristics: Characteristics | None = None,
        provenance: Provenance | None = None,
        relationship_id: str | None = None,
    ) -> Relationship:
        return self._model._connect(
            source,
            target,
            classification,
            characteristics=characteristics,
            provenance=provenance,
            relationship_id=relationship_id,
        )

    def __getitem__(self, relationship_id: str) -> Relationship:
        return self._model._relationship(relationship_id)

    def get(self, relationship_id: str) -> Relationship | None:
        if not isinstance(relationship_id, str):
            raise TypeError("relationship_id must be a string")
        return self._model._relationships.get(relationship_id)

    def all(self) -> tuple[Relationship, ...]:
        return tuple(self._model._relationships.values())


class AssemblyRegistry:
    """Model-bound registration and membership operations for assemblies."""

    __slots__ = ("_model",)

    def __init__(self, model: Model) -> None:
        self._model = model

    def add(self, assembly: Assembly) -> Assembly:
        return self._model._add_assembly(assembly)

    def include(
        self,
        assembly: Assembly | str,
        *members: AssemblyMember,
    ) -> Assembly:
        return self._model._change_assembly(assembly, include=members)

    def exclude(
        self,
        assembly: Assembly | str,
        *members: AssemblyMember,
    ) -> Assembly:
        return self._model._change_assembly(assembly, exclude=members)

    def __getitem__(self, assembly_id: str) -> Assembly:
        return self._model._resolve_assembly(assembly_id)

    def get(self, assembly_id: str) -> Assembly | None:
        if not isinstance(assembly_id, str):
            raise TypeError("assembly_id must be a string")
        entity = self._model._entities.get(assembly_id)
        return entity if isinstance(entity, Assembly) else None

    def all(self) -> tuple[Assembly, ...]:
        return tuple(
            entity
            for entity in self._model._entities.values()
            if isinstance(entity, Assembly)
        )

    def entities(self, assembly: Assembly | str) -> tuple[Entity, ...]:
        canonical = self._model._resolve_assembly(assembly)
        return tuple(sorted(canonical.entities, key=lambda entity: entity.entity_id))

    def relationships(
        self,
        assembly: Assembly | str,
    ) -> tuple[Relationship, ...]:
        canonical = self._model._resolve_assembly(assembly)
        return tuple(
            sorted(
                canonical.relationships,
                key=lambda relationship: relationship.relationship_id,
            )
        )

    def containing(
        self,
        member: Entity | Relationship,
    ) -> tuple[Assembly, ...]:
        if isinstance(member, Entity):
            canonical_entity = self._model._resolve_entity(member)
            return tuple(
                assembly
                for assembly in self.all()
                if canonical_entity in assembly.entities
            )
        if isinstance(member, Relationship):
            canonical_relationship = self._model._resolve_relationship(member)
            return tuple(
                assembly
                for assembly in self.all()
                if canonical_relationship in assembly.relationships
            )
        raise TypeError("member must be an Entity or Relationship")


class TaxonomyRegistry:
    """Model-bound registration and lookup for complete taxonomies."""

    __slots__ = ("_model",)

    def __init__(self, model: Model) -> None:
        self._model = model

    def add(self, taxonomy: Taxonomy) -> Taxonomy:
        return self._model._add_taxonomy(taxonomy)

    def __getitem__(self, code: str) -> Taxonomy:
        if not isinstance(code, str):
            raise TypeError("taxonomy code must be a string")
        try:
            return self._model._taxonomies[code]
        except KeyError as error:
            raise KeyError(f"unknown taxonomy code {code!r}") from error

    def get(self, code: str) -> Taxonomy | None:
        if not isinstance(code, str):
            raise TypeError("taxonomy code must be a string")
        return self._model._taxonomies.get(code)

    def all(self) -> tuple[Taxonomy, ...]:
        return tuple(self._model._taxonomies.values())
