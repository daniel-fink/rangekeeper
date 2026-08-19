from __future__ import annotations

from collections.abc import Iterable

from ..assembly import Assembly
from ..classification import Classification
from ..entity import Entity
from ..model import Model
from ..relationship import Relationship
from ..view import View
from .errors import SnapshotError


def select_source(
    source: Model | View,
) -> tuple[tuple[Entity, ...], tuple[Relationship, ...]]:
    if isinstance(source, Model):
        return source.entities(), source.relationships()
    if not isinstance(source, View):
        raise TypeError("source must be a Model or View")

    model = source.model
    entity_ids = set(source.entity_ids)
    relationship_ids = set(source.relationship_ids)
    pending: list[Assembly] = []
    for entity_id in entity_ids:
        entity = model.entity(entity_id)
        if isinstance(entity, Assembly):
            pending.append(entity)

    visited: set[str] = set()
    while pending:
        assembly = pending.pop()
        if assembly.entity_id in visited:
            continue
        visited.add(assembly.entity_id)
        for entity in assembly.entities:
            entity_ids.add(entity.entity_id)
            if isinstance(entity, Assembly):
                pending.append(entity)
        relationship_ids.update(
            relationship.relationship_id for relationship in assembly.relationships
        )
    for relationship_id in tuple(relationship_ids):
        relationship = model.relationship(relationship_id)
        entity_ids.update((relationship.source_id, relationship.target_id))

    return (
        tuple(entity for entity in model.entities() if entity.entity_id in entity_ids),
        tuple(
            relationship
            for relationship in model.relationships()
            if relationship.relationship_id in relationship_ids
        ),
    )


def required_classifications(
    entities: Iterable[Entity], relationships: Iterable[Relationship]
) -> tuple[Classification, ...]:
    by_key: dict[tuple[str | None, str], Classification] = {}

    def add(classification: Classification | None) -> None:
        if classification is None:
            return
        root = classification.root()
        for term in (root, *root.descendants()):
            existing = by_key.get(term.key)
            if existing is not None and existing is not term:
                raise SnapshotError(f"different Classifications share key {term.key!r}")
            by_key[term.key] = term

    for entity in entities:
        add(entity.classification)
        for values in entity.occupancy.values():
            for classification in values:
                add(classification)
    for relationship in relationships:
        add(relationship.classification)
        for values in relationship.characteristics.occupancy.values():
            for classification in values:
                add(classification)
    return tuple(by_key.values())
