from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol, TypeVar
from uuid import UUID

import networkx as nx

from .assembly import Assembly
from .classification import Classification
from .definitions import Definitions
from .entity import Entity
from .errors import (
    AmbiguousLookupError,
    IdentityConflictError,
    InvalidAssemblyError,
    MissingEntityError,
    MissingRelationshipError,
    _format_ids,
)
from .provenance import FactTarget, Provenance
from .relationship import Relationship
from .update import Update, _apply

if TYPE_CHECKING:
    from .view import View


__all__ = ["Graph"]


class _Identified(Protocol):
    id: UUID


_I = TypeVar("_I", bound=_Identified)
_H = TypeVar("_H", bound=Hashable)


def _index_by_id(items: Iterable[_I], kind: str) -> Mapping[UUID, _I]:
    """Build a frozen identity index and expose UUID collisions immediately."""

    result: dict[UUID, _I] = {}
    for item in items:
        if item.id in result:
            raise IdentityConflictError(f"duplicate {kind} UUID {item.id}")
        result[item.id] = item
    return MappingProxyType(result)


def _group_ids_by(
    items: Iterable[_I],
    key: Callable[[_I], _H | None],
) -> Mapping[_H, tuple[UUID, ...]]:
    """Group UUIDs without losing the source iterable's insertion order."""

    result: dict[_H, list[UUID]] = {}
    for item in items:
        value = key(item)
        if value is not None:
            result.setdefault(value, []).append(item.id)
    return MappingProxyType({value: tuple(ids) for value, ids in result.items()})


@dataclass(frozen=True, slots=True)
class Graph:
    """An immutable snapshot of canonical graph objects and their evidence."""

    definitions: Definitions = field(default_factory=Definitions)
    entities: tuple[Entity, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    provenance: Provenance = field(default_factory=Provenance)
    _entities_by_id: Mapping[UUID, Entity] = field(
        init=False, repr=False, compare=False
    )
    _relationships_by_id: Mapping[UUID, Relationship] = field(
        init=False, repr=False, compare=False
    )
    _graph_objects_by_id: Mapping[UUID, FactTarget] = field(
        init=False, repr=False, compare=False
    )
    _relationship_ids_by_source: Mapping[UUID, tuple[UUID, ...]] = field(
        init=False, repr=False, compare=False
    )
    _relationship_ids_by_target: Mapping[UUID, tuple[UUID, ...]] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.definitions, Definitions):
            raise TypeError("definitions must be Definitions")
        entities = tuple(self.entities)
        relationships = tuple(self.relationships)
        provenance = self.provenance
        if any(not isinstance(item, Entity) for item in entities):
            raise TypeError("entities must contain only Entity objects")
        if any(not isinstance(item, Relationship) for item in relationships):
            raise TypeError("relationships must contain only Relationship objects")
        if not isinstance(provenance, Provenance):
            raise TypeError("provenance must be Provenance")

        entities_by_id = _index_by_id(entities, "entity")
        relationships_by_id = _index_by_id(relationships, "relationship")
        owners = (*entities, *relationships)
        targets: tuple[FactTarget, ...] = (
            *entities,
            *relationships,
            *(item for owner in owners for item in owner.characteristics.items),
        )
        targets_by_id = _index_by_id(targets, "graph object")
        overlap = {
            identifier
            for identifier in targets_by_id
            if identifier in self.definitions._definition_by_id
        }
        if overlap:
            raise IdentityConflictError(
                f"definition and graph-object UUIDs overlap: {_format_ids(overlap)}"
            )

        self._validate_definition_references(entities, relationships)
        self._validate_relationships(relationships, entities_by_id)
        self._validate_assemblies(entities, relationships_by_id, entities_by_id)
        for fact in provenance.facts:
            target_id = fact.target.id
            registered = targets_by_id.get(target_id)
            if registered is None:
                raise ValueError(
                    f"Fact targets graph object {target_id} that is not present"
                )
            if registered is not fact.target:
                raise ValueError(
                    f"Fact target {target_id} is not the registered Graph instance"
                )

        object.__setattr__(self, "entities", entities)
        object.__setattr__(self, "relationships", relationships)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "_entities_by_id", entities_by_id)
        object.__setattr__(self, "_relationships_by_id", relationships_by_id)
        object.__setattr__(self, "_graph_objects_by_id", targets_by_id)
        object.__setattr__(
            self,
            "_relationship_ids_by_source",
            _group_ids_by(relationships, lambda item: item.source_id),
        )
        object.__setattr__(
            self,
            "_relationship_ids_by_target",
            _group_ids_by(relationships, lambda item: item.target_id),
        )

    @property
    def assemblies(self) -> tuple[Assembly, ...]:
        """Return assemblies in entity insertion order."""

        return tuple(item for item in self.entities if isinstance(item, Assembly))

    def entity(self, entity: str | UUID | Entity) -> Entity:
        """Resolve an entity code, UUID, or canonical instance."""

        if isinstance(entity, str):
            matches = tuple(item for item in self.entities if item.code == entity)
            if not matches:
                raise MissingEntityError(entity)
            if len(matches) > 1:
                raise AmbiguousLookupError(
                    f"entity code {entity!r} matches {len(matches)} entities"
                )
            return matches[0]
        else:
            entity_id = entity.id if isinstance(entity, Entity) else entity
        if not isinstance(entity_id, UUID):
            raise TypeError("entity lookup requires a code, Entity, or UUID")
        try:
            registered = self._entities_by_id[entity_id]
        except KeyError as error:
            raise MissingEntityError(entity_id) from error
        if isinstance(entity, Entity) and registered is not entity:
            raise IdentityConflictError(
                "the supplied Entity is not the registered Graph instance"
            )
        return registered

    def relationship(self, relationship: UUID | Relationship) -> Relationship:
        """Resolve a relationship UUID or canonical instance."""

        relationship_id = (
            relationship.id if isinstance(relationship, Relationship) else relationship
        )
        if not isinstance(relationship_id, UUID):
            raise TypeError("relationship lookup requires a Relationship or UUID")
        try:
            registered = self._relationships_by_id[relationship_id]
        except KeyError as error:
            raise MissingRelationshipError(relationship_id) from error
        if isinstance(relationship, Relationship) and registered is not relationship:
            raise IdentityConflictError(
                "the supplied Relationship is not the registered Graph instance"
            )
        return registered

    def apply(self, update: Update) -> Graph:
        """Return a new Graph with one validated update applied."""
        return _apply(self, update)

    def find_entities(
        self,
        *,
        code: str | None = None,
        name: str | None = None,
        classification: UUID | Classification | None = None,
    ) -> tuple[Entity, ...]:
        """Find entities matching all supplied semantic fields."""

        for value, label in ((code, "code"), (name, "name")):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{label} must be a string or None")
        requested = self.definitions._resolve_classification(classification)
        return tuple(
            entity
            for entity in self.entities
            if (code is None or entity.code == code)
            and (name is None or entity.name == name)
            and self.definitions._classification_matches(
                entity.classification,
                requested,
            )
        )

    def source_of(self, relationship: UUID | Relationship) -> Entity:
        """Return the canonical source entity for a relationship."""

        return self.entity(self.relationship(relationship).source_id)

    def target_of(self, relationship: UUID | Relationship) -> Entity:
        """Return the canonical target entity for a relationship."""

        return self.entity(self.relationship(relationship).target_id)

    def outgoing_relationships(
        self,
        entity: str | UUID | Entity,
        *,
        classification: UUID | Classification | None = None,
    ) -> tuple[Relationship, ...]:
        """Return outgoing relationships, optionally including classification descendants."""

        return self._relationships_for(
            entity,
            index=self._relationship_ids_by_source,
            classification=classification,
        )

    def incoming_relationships(
        self,
        entity: str | UUID | Entity,
        *,
        classification: UUID | Classification | None = None,
    ) -> tuple[Relationship, ...]:
        """Return incoming relationships, optionally including classification descendants."""

        return self._relationships_for(
            entity,
            index=self._relationship_ids_by_target,
            classification=classification,
        )

    def relationships_between(
        self,
        source: str | UUID | Entity,
        target: str | UUID | Entity,
        *,
        classification: UUID | Classification | None = None,
    ) -> tuple[Relationship, ...]:
        """Return directed relationships from source to target."""

        source_entity = self.entity(source)
        target_entity = self.entity(target)
        return tuple(
            relationship
            for relationship in self.outgoing_relationships(
                source_entity, classification=classification
            )
            if relationship.target_id == target_entity.id
        )

    def entities_in(self, assembly: str | UUID | Assembly) -> tuple[Entity, ...]:
        """Return an assembly's entity members in Graph insertion order."""

        registered = self.entity(assembly)
        if not isinstance(registered, Assembly):
            raise TypeError("assembly must resolve to an Assembly")
        return tuple(
            entity for entity in self.entities if entity.id in registered.entity_ids
        )

    def relationships_in(
        self, assembly: str | UUID | Assembly
    ) -> tuple[Relationship, ...]:
        """Return an assembly's relationship members in Graph insertion order."""

        registered = self.entity(assembly)
        if not isinstance(registered, Assembly):
            raise TypeError("assembly must resolve to an Assembly")
        return tuple(
            relationship
            for relationship in self.relationships
            if relationship.id in registered.relationship_ids
        )

    def view(
        self,
        *,
        entities: Iterable[str | UUID | Entity] | None = None,
        relationships: Iterable[UUID | Relationship] | None = None,
        assembly: str | UUID | Assembly | None = None,
    ) -> View:
        """Select graph membership; apply semantic constraints later with View.filter()."""

        from .view import View

        return View(
            self,
            entities=entities,
            relationships=relationships,
            assembly=assembly,
        )

    def _relationships_for(
        self,
        entity: str | UUID | Entity,
        *,
        index: Mapping[UUID, tuple[UUID, ...]],
        classification: UUID | Classification | None,
    ) -> tuple[Relationship, ...]:
        registered = self.entity(entity)
        requested = self.definitions._resolve_classification(classification)
        return tuple(
            relationship
            for identifier in index.get(registered.id, ())
            if self.definitions._classification_matches(
                (relationship := self._relationships_by_id[identifier]).classification,
                requested,
            )
        )

    def _validate_definition_references(
        self,
        entities: tuple[Entity, ...],
        relationships: tuple[Relationship, ...],
    ) -> None:
        for owner in (*entities, *relationships):
            if owner.classification is not None:
                self.definitions._resolve_classification(owner.classification)
            for label in owner.characteristics.labels.values():
                for classification in label.classifications:
                    self.definitions._resolve_classification(classification)
            for measurement in owner.characteristics.measurements.values():
                self.definitions._resolve_measure(measurement.measure)

    @staticmethod
    def _validate_relationships(
        relationships: tuple[Relationship, ...],
        entities_by_id: Mapping[UUID, Entity],
    ) -> None:
        for relationship in relationships:
            if relationship.source_id not in entities_by_id:
                raise MissingEntityError(relationship.source_id)
            if relationship.target_id not in entities_by_id:
                raise MissingEntityError(relationship.target_id)

    @staticmethod
    def _validate_assemblies(
        entities: tuple[Entity, ...],
        relationships_by_id: Mapping[UUID, Relationship],
        entities_by_id: Mapping[UUID, Entity],
    ) -> None:
        """Validate exact membership and reject recursive assembly ownership."""

        assemblies = tuple(item for item in entities if isinstance(item, Assembly))
        assembly_graph = nx.DiGraph()
        assembly_graph.add_nodes_from(item.id for item in assemblies)
        for assembly in assemblies:
            missing_entities = assembly.entity_ids.difference(entities_by_id)
            missing_relationships = assembly.relationship_ids.difference(
                relationships_by_id
            )
            if missing_entities or missing_relationships:
                raise InvalidAssemblyError("assembly references missing graph members")
            allowed_endpoints = {assembly.id, *assembly.entity_ids}
            for relationship_id in assembly.relationship_ids:
                relationship = relationships_by_id[relationship_id]
                if (
                    relationship.source_id not in allowed_endpoints
                    or relationship.target_id not in allowed_endpoints
                ):
                    raise InvalidAssemblyError(
                        "assembly relationship endpoint is not a member"
                    )
            assembly_graph.add_edges_from(
                (assembly.id, member_id)
                for member_id in assembly.entity_ids
                if isinstance(entities_by_id[member_id], Assembly)
            )
        if not nx.is_directed_acyclic_graph(assembly_graph):
            raise InvalidAssemblyError("assembly membership cannot contain cycles")
