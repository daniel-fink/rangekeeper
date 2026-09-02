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
class Update:
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
        _validate(self)


def _validate(update: Update) -> None:
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
    entities = dict(graph._entities_by_id)
    relationships = dict(graph._relationships_by_id)
    facts = dict(graph._facts_by_target_id)

    entity_removals = update.remove_entity_ids
    relationship_removals = set(update.remove_relationship_ids)
    fact_removals = set(update.remove_fact_target_ids)

    missing_fact_targets = fact_removals.difference(facts)
    if missing_fact_targets:
        raise KeyError(
            f"cannot remove missing Fact targets: {_format_ids(missing_fact_targets)}"
        )
    for relationship_id in update.remove_relationship_ids:
        if relationship_id not in relationships:
            raise MissingRelationshipError(relationship_id)

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
        if not update.cascade and (incident or memberships or dependent_facts):
            raise ValueError(
                f"entity {entity_id} has dependent relationships, assembly membership, or Facts; use cascade=True"
            )
        if update.cascade:
            relationship_removals.update(incident)
            fact_removals.update({entity_id, *characteristic_ids})

    for relationship_id in relationship_removals:
        relationship = relationships[relationship_id]
        if update.cascade:
            fact_removals.add(relationship_id)
            fact_removals.update(item.id for item in relationship.characteristics.items)

    if update.cascade and (entity_removals or relationship_removals):
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

    for entity in update.add_entities:
        if entity.id in entities:
            raise IdentityConflictError(f"cannot add existing entity UUID {entity.id}")
    for entity in update.replace_entities:
        if entity.id not in entities:
            raise KeyError(f"cannot replace missing entity UUID {entity.id}")
    for relationship in update.add_relationships:
        if relationship.id in relationships:
            raise IdentityConflictError(
                f"cannot add existing relationship UUID {relationship.id}"
            )
    for relationship in update.replace_relationships:
        if relationship.id not in relationships:
            raise KeyError(
                f"cannot replace missing relationship UUID {relationship.id}"
            )
    for fact in update.add_facts:
        if fact.target.id in facts:
            raise IdentityConflictError(
                f"cannot add existing Fact target {fact.target.id}"
            )
    for fact in update.replace_facts:
        if fact.target.id not in facts:
            raise KeyError(f"cannot replace missing Fact target {fact.target.id}")

    entities.update(
        (item.id, item) for item in (*update.add_entities, *update.replace_entities)
    )
    relationships.update(
        (item.id, item)
        for item in (*update.add_relationships, *update.replace_relationships)
    )
    facts.update(
        (item.target.id, item) for item in (*update.add_facts, *update.replace_facts)
    )

    from .graph import Graph

    return Graph(
        definitions=definitions,
        entities=tuple(entities.values()),
        relationships=tuple(relationships.values()),
        provenance=tuple(facts.values()),
    )
