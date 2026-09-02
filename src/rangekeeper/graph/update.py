from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any
from uuid import UUID

from .assembly import Assembly
from .definitions import Definitions
from .entity import Entity
from .errors import (
    IdentityConflictError,
    MissingEntityError,
    MissingRelationshipError,
    _format_ids,
)
from .provenance import Fact
from .relationship import Relationship

if TYPE_CHECKING:
    from .graph import Graph


@dataclass(frozen=True, slots=True)
class GraphChange:
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
        tuple_fields = (
            "add_entities",
            "replace_entities",
            "add_relationships",
            "replace_relationships",
            "add_facts",
            "replace_facts",
        )
        for name in tuple_fields:
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for name in ("add_entities", "replace_entities"):
            if any(not isinstance(item, Entity) for item in getattr(self, name)):
                raise TypeError(f"{name} must contain only Entity objects")
        for name in ("add_relationships", "replace_relationships"):
            if any(not isinstance(item, Relationship) for item in getattr(self, name)):
                raise TypeError(f"{name} must contain only Relationship objects")
        for name in ("add_facts", "replace_facts"):
            if any(not isinstance(item, Fact) for item in getattr(self, name)):
                raise TypeError(f"{name} must contain only Fact objects")
        set_fields = (
            "remove_entity_ids",
            "remove_relationship_ids",
            "remove_fact_target_ids",
        )
        for name in set_fields:
            values = frozenset(getattr(self, name))
            if any(not isinstance(value, UUID) for value in values):
                raise TypeError(f"{name} must contain only UUIDs")
            object.__setattr__(self, name, values)
        if self.definitions is not None and not isinstance(
            self.definitions, Definitions
        ):
            raise TypeError("definitions must be Definitions or None")
        if not isinstance(self.cascade, bool):
            raise TypeError("cascade must be a bool")


def _apply_change(graph: Graph, change: GraphChange) -> Graph:
    """Validate and apply one complete change without mutating the Graph."""
    if not isinstance(change, GraphChange):
        raise TypeError("change must be a GraphChange")
    definitions = (
        graph.definitions if change.definitions is None else change.definitions
    )
    entities = dict(graph._entities_by_id)
    relationships = dict(graph._relationships_by_id)
    facts = dict(graph._facts_by_target_id)

    _validate_operations(
        additions={item.id for item in change.add_entities},
        replacements={item.id for item in change.replace_entities},
        removals=change.remove_entity_ids,
        label="entity",
    )
    _validate_operations(
        additions={item.id for item in change.add_relationships},
        replacements={item.id for item in change.replace_relationships},
        removals=change.remove_relationship_ids,
        label="relationship",
    )
    _validate_operations(
        additions={item.target.id for item in change.add_facts},
        replacements={item.target.id for item in change.replace_facts},
        removals=change.remove_fact_target_ids,
        label="Fact",
    )

    relationship_removals = set(change.remove_relationship_ids)
    fact_removals = set(change.remove_fact_target_ids)
    entity_removals = set(change.remove_entity_ids)

    missing_fact_targets = fact_removals.difference(facts)
    if missing_fact_targets:
        raise KeyError(
            f"cannot remove missing Fact targets: {_format_ids(missing_fact_targets)}"
        )

    for entity_id in entity_removals:
        if entity_id not in entities:
            raise MissingEntityError(entity_id)
        entity = entities[entity_id]
        characteristic_ids = {item.id for item in entity.characteristics.items}
        incident = {
            relationship.id
            for relationship in relationships.values()
            if relationship.source_id == entity_id
            or relationship.target_id == entity_id
        }
        memberships = {
            assembly.id
            for assembly in entities.values()
            if isinstance(assembly, Assembly) and entity_id in assembly.entity_ids
        }
        dependent_facts = {entity_id, *characteristic_ids}.intersection(facts)
        if not change.cascade and (incident or memberships or dependent_facts):
            raise ValueError(
                f"entity {entity_id} has dependent relationships, assembly membership, or Facts; use cascade=True"
            )
        if change.cascade:
            relationship_removals.update(incident)
            fact_removals.update({entity_id, *characteristic_ids})

    for relationship_id in relationship_removals:
        if relationship_id not in relationships:
            if relationship_id in change.remove_relationship_ids:
                raise MissingRelationshipError(relationship_id)
            continue
        relationship = relationships[relationship_id]
        if change.cascade:
            fact_removals.add(relationship_id)
            fact_removals.update(item.id for item in relationship.characteristics.items)

    if change.cascade and (entity_removals or relationship_removals):
        for entity_id, entity in tuple(entities.items()):
            if not isinstance(entity, Assembly) or entity_id in entity_removals:
                continue
            next_entity_ids = entity.entity_ids.difference(entity_removals)
            next_relationship_ids = entity.relationship_ids.difference(
                relationship_removals
            )
            if (
                next_entity_ids != entity.entity_ids
                or next_relationship_ids != entity.relationship_ids
            ):
                entities[entity_id] = replace(
                    entity,
                    entity_ids=frozenset(next_entity_ids),
                    relationship_ids=frozenset(next_relationship_ids),
                )
                fact_removals.add(entity_id)

    for identifier in entity_removals:
        entities.pop(identifier)
    for identifier in relationship_removals:
        relationships.pop(identifier)
    for identifier in fact_removals:
        facts.pop(identifier, None)

    _apply_additions(entities, change.add_entities, "entity")
    _apply_replacements(entities, change.replace_entities, "entity")
    _apply_additions(relationships, change.add_relationships, "relationship")
    _apply_replacements(relationships, change.replace_relationships, "relationship")
    _apply_fact_additions(facts, change.add_facts)
    _apply_fact_replacements(facts, change.replace_facts)

    from .graph import Graph

    return Graph(
        definitions=definitions,
        entities=tuple(entities.values()),
        relationships=tuple(relationships.values()),
        provenance=tuple(facts.values()),
    )


def _apply_additions(
    registry: dict[UUID, Any], additions: tuple[Any, ...], label: str
) -> None:
    seen: set[UUID] = set()
    for item in additions:
        if item.id in seen or item.id in registry:
            raise IdentityConflictError(f"cannot add existing {label} UUID {item.id}")
        seen.add(item.id)
        registry[item.id] = item


def _apply_replacements(
    registry: dict[UUID, Any], replacements: tuple[Any, ...], label: str
) -> None:
    seen: set[UUID] = set()
    for item in replacements:
        if item.id in seen:
            raise IdentityConflictError(f"replacement repeats {label} UUID {item.id}")
        if item.id not in registry:
            raise KeyError(f"cannot replace missing {label} UUID {item.id}")
        seen.add(item.id)
        registry[item.id] = item


def _apply_fact_additions(
    registry: dict[UUID, Fact[Any]], additions: tuple[Fact[Any], ...]
) -> None:
    for fact in additions:
        if fact.target.id in registry:
            raise IdentityConflictError(
                f"cannot add existing Fact target {fact.target.id}"
            )
        registry[fact.target.id] = fact


def _apply_fact_replacements(
    registry: dict[UUID, Fact[Any]], replacements: tuple[Fact[Any], ...]
) -> None:
    for fact in replacements:
        if fact.target.id not in registry:
            raise KeyError(f"cannot replace missing Fact target {fact.target.id}")
        registry[fact.target.id] = fact


def _validate_operations(
    *,
    additions: set[UUID],
    replacements: set[UUID],
    removals: set[UUID] | frozenset[UUID],
    label: str,
) -> None:
    if additions.intersection(replacements):
        raise ValueError(f"the same {label} UUID cannot be added and replaced")
    if additions.intersection(removals):
        raise ValueError(f"the same {label} UUID cannot be added and removed")
    if replacements.intersection(removals):
        raise ValueError(f"the same {label} UUID cannot be removed and replaced")
