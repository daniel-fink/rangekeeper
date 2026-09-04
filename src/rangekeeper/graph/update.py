from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any
from uuid import UUID

from .assembly import Assembly
from .definitions import Definitions
from .entity import Entity
from .errors import (
    GraphDependencyError,
    IdentityConflictError,
    MissingEntityError,
    MissingFactError,
    MissingRelationshipError,
)
from .provenance import Fact, Provenance
from .relationship import Relationship

if TYPE_CHECKING:
    from .graph import Graph


__all__ = ["Update"]


@dataclass(frozen=True, slots=True)
class Update:
    """A complete atomic transaction for constructing a replacement Graph."""

    definitions: Definitions | None = None
    add_entities: tuple[Entity, ...] = ()
    replace_entities: tuple[Entity, ...] = ()
    remove_entity_ids: frozenset[UUID] = frozenset()
    add_relationships: tuple[Relationship, ...] = ()
    replace_relationships: tuple[Relationship, ...] = ()
    remove_relationship_ids: frozenset[UUID] = frozenset()
    add_facts: tuple[Fact[Any], ...] = ()
    replace_facts: tuple[Fact[Any], ...] = ()
    remove_fact_target_ids: frozenset[UUID] = frozenset()
    cascade: bool = False

    def __post_init__(self) -> None:
        for name in (
            "add_entities",
            "replace_entities",
            "add_relationships",
            "replace_relationships",
            "add_facts",
            "replace_facts",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for name in (
            "remove_entity_ids",
            "remove_relationship_ids",
            "remove_fact_target_ids",
        ):
            object.__setattr__(self, name, frozenset(getattr(self, name)))
        _validate_update_shape(self)
        _validate_operation_conflicts(self)


@dataclass(slots=True)
class _RemovalScope:
    """Track every object removed explicitly or through cascading."""

    entity_ids: set[UUID]
    relationship_ids: set[UUID]
    fact_target_ids: set[UUID]

    @classmethod
    def from_update(cls, update: Update) -> _RemovalScope:
        """Copy an Update's immutable removal requests into a mutable scope."""

        return cls(
            entity_ids=set(update.remove_entity_ids),
            relationship_ids=set(update.remove_relationship_ids),
            fact_target_ids=set(update.remove_fact_target_ids),
        )


@dataclass(slots=True)
class _Candidate:
    """Hold the isolated graph state assembled by an Update."""

    definitions: Definitions
    entities: dict[UUID, Entity]
    relationships: dict[UUID, Relationship]
    facts: dict[UUID, Fact[Any]]

    @classmethod
    def from_graph(
        cls,
        graph: Graph,
        *,
        definitions: Definitions,
    ) -> _Candidate:
        """Copy a Graph so transaction planning cannot mutate its source."""

        return cls(
            definitions=definitions,
            entities=dict(graph._entities_by_id),
            relationships=dict(graph._relationships_by_id),
            facts={fact.target.id: fact for fact in graph.provenance.facts},
        )

    def overlay(self, update: Update) -> None:
        """Apply explicit replacements and additions in stable insertion order."""

        self.entities.update((item.id, item) for item in update.replace_entities)
        self.entities.update((item.id, item) for item in update.add_entities)
        self.relationships.update(
            (item.id, item) for item in update.replace_relationships
        )
        self.relationships.update((item.id, item) for item in update.add_relationships)
        self.facts.update((item.target.id, item) for item in update.replace_facts)
        self.facts.update((item.target.id, item) for item in update.add_facts)

    def remove(self, removals: _RemovalScope) -> None:
        """Remove every object in scope from this isolated candidate."""

        for identifier in removals.entity_ids:
            self.entities.pop(identifier)
        for identifier in removals.relationship_ids:
            self.relationships.pop(identifier)
        for identifier in removals.fact_target_ids:
            self.facts.pop(identifier, None)

    def build(self) -> Graph:
        """Construct the replacement only after candidate validation succeeds."""

        from .graph import Graph

        return Graph(
            definitions=self.definitions,
            entities=tuple(self.entities.values()),
            relationships=tuple(self.relationships.values()),
            provenance=Provenance(facts=tuple(self.facts.values())),
        )


def _validate_update_shape(update: Update) -> None:
    """Normalize type expectations before considering Graph state."""

    for name, expected in (
        ("add_entities", Entity),
        ("replace_entities", Entity),
        ("add_relationships", Relationship),
        ("replace_relationships", Relationship),
        ("add_facts", Fact),
        ("replace_facts", Fact),
    ):
        if any(not isinstance(item, expected) for item in getattr(update, name)):
            raise TypeError(f"{name} must contain only {expected.__name__} objects")
    for name in (
        "remove_entity_ids",
        "remove_relationship_ids",
        "remove_fact_target_ids",
    ):
        if any(not isinstance(value, UUID) for value in getattr(update, name)):
            raise TypeError(f"{name} must contain only UUIDs")
    if update.definitions is not None and not isinstance(
        update.definitions, Definitions
    ):
        raise TypeError("definitions must be Definitions or None")
    if not isinstance(update.cascade, bool):
        raise TypeError("cascade must be a bool")


def _validate_operation_conflicts(update: Update) -> None:
    """Reject ambiguous instructions for the same stable UUID."""

    operations = (
        (
            "entity",
            tuple(item.id for item in update.add_entities),
            tuple(item.id for item in update.replace_entities),
            update.remove_entity_ids,
        ),
        (
            "relationship",
            tuple(item.id for item in update.add_relationships),
            tuple(item.id for item in update.replace_relationships),
            update.remove_relationship_ids,
        ),
        (
            "Fact target",
            tuple(item.target.id for item in update.add_facts),
            tuple(item.target.id for item in update.replace_facts),
            update.remove_fact_target_ids,
        ),
    )
    for label, additions, replacements, removals in operations:
        for operation, identifiers in (
            ("addition", additions),
            ("replacement", replacements),
        ):
            seen: set[UUID] = set()
            for identifier in identifiers:
                if identifier in seen:
                    raise IdentityConflictError(
                        f"{operation} repeats {label} UUID {identifier}"
                    )
                seen.add(identifier)
        addition_ids = set(additions)
        replacement_ids = set(replacements)
        if addition_ids.intersection(replacement_ids):
            raise ValueError(f"the same {label} UUID cannot be added and replaced")
        if addition_ids.intersection(removals):
            raise ValueError(f"the same {label} UUID cannot be added and removed")
        if replacement_ids.intersection(removals):
            raise ValueError(f"the same {label} UUID cannot be removed and replaced")


def _apply(graph: Graph, update: Update) -> Graph:
    """Apply one complete Update without mutating the Graph."""
    if not isinstance(update, Update):
        raise TypeError("update must be an Update")

    definitions = (
        graph.definitions if update.definitions is None else update.definitions
    )
    candidate = _Candidate.from_graph(graph, definitions=definitions)
    _validate_operations_against_source(candidate, update)
    candidate.overlay(update)
    removals = _RemovalScope.from_update(update)

    if update.cascade:
        _expand_cascade(graph, update, candidate, removals)

    candidate.remove(removals)
    _validate_remaining_dependencies(graph, candidate, removals)

    return candidate.build()


def _validate_operations_against_source(
    candidate: _Candidate,
    update: Update,
) -> None:
    """Ensure each operation agrees with the source Graph's current state."""

    current_entities = candidate.entities
    current_relationships = candidate.relationships
    current_facts = candidate.facts

    for entity in update.add_entities:
        if entity.id in current_entities:
            raise IdentityConflictError(f"cannot add existing entity UUID {entity.id}")
    for entity in update.replace_entities:
        if entity.id not in current_entities:
            raise MissingEntityError(entity.id)
    for identifier in update.remove_entity_ids:
        if identifier not in current_entities:
            raise MissingEntityError(identifier)

    for relationship in update.add_relationships:
        if relationship.id in current_relationships:
            raise IdentityConflictError(
                f"cannot add existing relationship UUID {relationship.id}"
            )
    for relationship in update.replace_relationships:
        if relationship.id not in current_relationships:
            raise MissingRelationshipError(relationship.id)
    for identifier in update.remove_relationship_ids:
        if identifier not in current_relationships:
            raise MissingRelationshipError(identifier)

    for fact in update.add_facts:
        if fact.target.id in current_facts:
            raise IdentityConflictError(
                f"cannot add existing Fact target {fact.target.id}"
            )
    for fact in update.replace_facts:
        if fact.target.id not in current_facts:
            raise MissingFactError(fact.target.id)
    for identifier in update.remove_fact_target_ids:
        if identifier not in current_facts:
            raise MissingFactError(identifier)


def _expand_cascade(
    graph: Graph,
    update: Update,
    candidate: _Candidate,
    removals: _RemovalScope,
) -> None:
    """Clean existing dependencies without silently discarding caller input."""

    _cascade_relationships(update, candidate, removals)
    removed_target_ids = _removed_graph_object_ids(graph, removals)
    _cascade_facts(update, candidate, removals, removed_target_ids)
    _cascade_assemblies(update, candidate, removals)


def _cascade_relationships(
    update: Update,
    candidate: _Candidate,
    removals: _RemovalScope,
) -> None:
    """Remove existing relationships incident to deleted entities."""

    protected_relationships = {
        item.id for item in (*update.add_relationships, *update.replace_relationships)
    }
    for relationship in candidate.relationships.values():
        removed_endpoints = {
            relationship.source_id,
            relationship.target_id,
        }.intersection(removals.entity_ids)
        if not removed_endpoints:
            continue
        if relationship.id in protected_relationships:
            target_id = min(removed_endpoints, key=str)
            raise GraphDependencyError(
                "entity",
                target_id,
                relationship_ids=(relationship.id,),
            )
        removals.relationship_ids.add(relationship.id)


def _cascade_facts(
    update: Update,
    candidate: _Candidate,
    removals: _RemovalScope,
    removed_target_ids: set[UUID],
) -> None:
    """Remove evidence whose graph object no longer survives."""

    protected_fact_targets = {
        item.target.id for item in (*update.add_facts, *update.replace_facts)
    }
    conflicting_facts = removed_target_ids.intersection(protected_fact_targets)
    if conflicting_facts:
        target_id = min(conflicting_facts, key=str)
        raise GraphDependencyError(
            "graph object",
            target_id,
            fact_target_ids=(target_id,),
        )
    removals.fact_target_ids.update(removed_target_ids.intersection(candidate.facts))


def _cascade_assemblies(
    update: Update,
    candidate: _Candidate,
    removals: _RemovalScope,
) -> None:
    """Clean membership in unmodified surviving Assemblies."""

    protected_entities = {
        item.id for item in (*update.add_entities, *update.replace_entities)
    }
    protected_fact_targets = {
        item.target.id for item in (*update.add_facts, *update.replace_facts)
    }
    for entity_id, entity in tuple(candidate.entities.items()):
        if not isinstance(entity, Assembly) or entity_id in removals.entity_ids:
            continue
        next_entity_ids = entity.entity_ids.difference(removals.entity_ids)
        next_relationship_ids = entity.relationship_ids.difference(
            removals.relationship_ids
        )
        if (
            next_entity_ids == entity.entity_ids
            and next_relationship_ids == entity.relationship_ids
        ):
            continue
        if entity_id in protected_entities:
            raise GraphDependencyError(
                "assembly",
                entity_id,
                relationship_ids=entity.relationship_ids.intersection(
                    removals.relationship_ids
                ),
                assembly_ids=(entity_id,),
            )
        if entity_id in protected_fact_targets:
            raise GraphDependencyError(
                "assembly",
                entity_id,
                fact_target_ids=(entity_id,),
            )
        candidate.entities[entity_id] = replace(
            entity,
            entity_ids=frozenset(next_entity_ids),
            relationship_ids=frozenset(next_relationship_ids),
        )
        removals.fact_target_ids.add(entity_id)


def _removed_graph_object_ids(
    graph: Graph,
    removals: _RemovalScope,
) -> set[UUID]:
    """Include characteristics owned by removed entities and relationships."""

    identifiers = removals.entity_ids.union(removals.relationship_ids)
    owners = (
        *(graph._entities_by_id[identifier] for identifier in removals.entity_ids),
        *(
            graph._relationships_by_id[identifier]
            for identifier in removals.relationship_ids
        ),
    )
    for owner in owners:
        identifiers.update(item.id for item in owner.characteristics.items)
    return identifiers


def _validate_remaining_dependencies(
    graph: Graph,
    candidate: _Candidate,
    removals: _RemovalScope,
) -> None:
    """Reject a candidate that still refers to anything scheduled for removal."""

    removed_object_ids = _removed_graph_object_ids(graph, removals)
    remaining_fact_targets = removed_object_ids.intersection(candidate.facts)

    for entity_id in sorted(removals.entity_ids, key=str):
        incident = {
            relationship.id
            for relationship in candidate.relationships.values()
            if relationship.source_id == entity_id
            or relationship.target_id == entity_id
        }
        memberships = {
            assembly.id
            for assembly in candidate.entities.values()
            if isinstance(assembly, Assembly) and entity_id in assembly.entity_ids
        }
        fact_targets = {
            entity_id,
            *(
                item.id
                for item in graph._graph_objects_by_id[entity_id].characteristics.items
            ),
        }.intersection(remaining_fact_targets)
        if incident or memberships or fact_targets:
            raise GraphDependencyError(
                "entity",
                entity_id,
                relationship_ids=incident,
                assembly_ids=memberships,
                fact_target_ids=fact_targets,
            )

    for relationship_id in sorted(removals.relationship_ids, key=str):
        memberships = {
            assembly.id
            for assembly in candidate.entities.values()
            if isinstance(assembly, Assembly)
            and relationship_id in assembly.relationship_ids
        }
        relationship = graph._graph_objects_by_id[relationship_id]
        target_ids = {relationship_id}
        assert isinstance(relationship, Relationship)
        target_ids.update(item.id for item in relationship.characteristics.items)
        fact_targets = target_ids.intersection(remaining_fact_targets)
        if memberships or fact_targets:
            raise GraphDependencyError(
                "relationship",
                relationship_id,
                assembly_ids=memberships,
                fact_target_ids=fact_targets,
            )
