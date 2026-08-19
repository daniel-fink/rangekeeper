from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import networkx as nx

from .classification import Classification
from .entity import Entity
from .errors import MissingEntityError
from .relationship import Relationship

if TYPE_CHECKING:
    from .model import Model


@dataclass(frozen=True)
class View:
    """An immutable selection of registered Model entity and relationship IDs."""

    model: Model
    entity_ids: frozenset[str]
    relationship_ids: frozenset[str]

    def __post_init__(self) -> None:
        from .model import Model

        if not isinstance(self.model, Model):
            raise TypeError("model must be a Model")
        object.__setattr__(self, "entity_ids", frozenset(self.entity_ids))
        object.__setattr__(self, "relationship_ids", frozenset(self.relationship_ids))
        for entity_id in self.entity_ids:
            self.model.entity(entity_id)
        for relationship_id in self.relationship_ids:
            relationship = self.model.relationship(relationship_id)
            if (
                relationship.source_id not in self.entity_ids
                or relationship.target_id not in self.entity_ids
            ):
                raise ValueError(
                    f"view relationship {relationship_id!r} has an endpoint outside the View"
                )

    def entities(self) -> tuple[Entity, ...]:
        return tuple(
            entity
            for entity in self.model.entities()
            if entity.entity_id in self.entity_ids
        )

    def relationships(self) -> tuple[Relationship, ...]:
        return tuple(
            relationship
            for relationship in self.model.relationships()
            if relationship.relationship_id in self.relationship_ids
        )

    def filter(
        self,
        *,
        entity_classification: Classification | str | None = None,
        relationship_classification: Classification | str | None = None,
        predicate: Callable[[Entity], bool] | None = None,
    ) -> View:
        return self.model._filtered_view(
            entity_ids=self.entity_ids,
            relationship_ids=self.relationship_ids,
            entity_classification=entity_classification,
            relationship_classification=relationship_classification,
            predicate=predicate,
        )

    def expand(
        self,
        relationship: Classification | str | None = None,
        *,
        outgoing: bool = True,
        incoming: bool = True,
    ) -> View:
        self.model._classification_matches(None, relationship)
        if not outgoing and not incoming:
            raise ValueError("expand requires outgoing or incoming relationships")
        expanded_entity_ids = set(self.entity_ids)
        expanded_relationship_ids = set(self.relationship_ids)
        for edge in self.model.relationships():
            if not self.model._classification_matches(
                edge.classification, relationship
            ):
                continue
            if outgoing and edge.source_id in self.entity_ids:
                expanded_entity_ids.add(edge.target_id)
                expanded_relationship_ids.add(edge.relationship_id)
            if incoming and edge.target_id in self.entity_ids:
                expanded_entity_ids.add(edge.source_id)
                expanded_relationship_ids.add(edge.relationship_id)
        return View(
            model=self.model,
            entity_ids=frozenset(expanded_entity_ids),
            relationship_ids=frozenset(expanded_relationship_ids),
        )

    def predecessors(
        self,
        entity: Entity | str,
        relationship: Classification | str | None = None,
    ) -> tuple[Entity, ...]:
        entity_id = self._resolve_view_entity_id(entity)
        return self.model._predecessors(
            entity_id,
            relationship,
            entity_ids=self.entity_ids,
            relationship_ids=self.relationship_ids,
        )

    def successors(
        self,
        entity: Entity | str,
        relationship: Classification | str | None = None,
    ) -> tuple[Entity, ...]:
        entity_id = self._resolve_view_entity_id(entity)
        return self.model._successors(
            entity_id,
            relationship,
            entity_ids=self.entity_ids,
            relationship_ids=self.relationship_ids,
        )

    def roots(self) -> tuple[Entity, ...]:
        targets = {relationship.target_id for relationship in self.relationships()}
        return tuple(
            entity for entity in self.entities() if entity.entity_id not in targets
        )

    def leaves(self) -> tuple[Entity, ...]:
        sources = {relationship.source_id for relationship in self.relationships()}
        return tuple(
            entity for entity in self.entities() if entity.entity_id not in sources
        )

    def is_arborescence(self) -> bool:
        graph = self.to_networkx()
        return bool(graph) and nx.is_arborescence(graph)

    def to_networkx(self) -> nx.MultiDiGraph:
        graph = nx.MultiDiGraph()
        for entity in self.entities():
            graph.add_node(entity.entity_id, entity=entity)
        for relationship in self.relationships():
            graph.add_edge(
                relationship.source_id,
                relationship.target_id,
                key=relationship.relationship_id,
                relationship=relationship,
            )
        return nx.freeze(graph)

    def _resolve_view_entity_id(self, entity: Entity | str) -> str:
        canonical = self.model._resolve_entity(entity)
        if canonical.entity_id not in self.entity_ids:
            raise MissingEntityError(canonical.entity_id)
        return canonical.entity_id
