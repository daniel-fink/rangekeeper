from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

import networkx as nx

from .assembly import Assembly
from .aggregation import Aggregation
from .classification import Classification
from .entity import Entity
from .errors import MissingEntityError
from .graph import Graph, _to_networkx
from .reduce import Reduction
from .relationship import Relationship


T = TypeVar("T")


@dataclass(frozen=True, init=False, slots=True)
class View:
    graph: Graph
    _entity_ids: frozenset[UUID]
    _relationship_ids: frozenset[UUID]

    def __init__(
        self,
        graph: Graph,
        *,
        entities: Iterable[str | UUID | Entity] | None = None,
        relationships: Iterable[UUID | Relationship] | None = None,
        entity_classification: UUID | Classification | None = None,
        relationship_classification: UUID | Classification | None = None,
        assembly: str | UUID | Assembly | None = None,
        predicate: Callable[[Entity], bool] | None = None,
    ) -> None:
        if not isinstance(graph, Graph):
            raise TypeError("graph must be a Graph")
        if assembly is not None and (entities is not None or relationships is not None):
            raise ValueError("assembly and explicit selections are mutually exclusive")
        if predicate is not None and not callable(predicate):
            raise TypeError("predicate must be callable or None")

        preserve_entity_id: UUID | None = None
        if assembly is not None:
            candidate = graph.entity(assembly)
            if not isinstance(candidate, Assembly):
                raise TypeError("assembly must resolve to an Assembly")
            preserve_entity_id = candidate.id
            selected_entity_ids = {candidate.id, *candidate.entity_ids}
            selected_relationship_ids = set(candidate.relationship_ids)
        elif entities is None and relationships is None:
            selected_entity_ids = set(graph._entities_by_id)
            selected_relationship_ids = set(graph._relationships_by_id)
        elif entities is not None and relationships is None:
            selected_entity_ids = {graph.entity(item).id for item in entities}
            selected_relationship_ids = {
                relationship.id
                for relationship in graph.relationships
                if relationship.source_id in selected_entity_ids
                and relationship.target_id in selected_entity_ids
            }
        elif entities is None:
            selected_relationship_ids = {
                graph.relationship(item).id for item in relationships or ()
            }
            selected_entity_ids = {
                endpoint
                for identifier in selected_relationship_ids
                for endpoint in (
                    graph._relationships_by_id[identifier].source_id,
                    graph._relationships_by_id[identifier].target_id,
                )
            }
        else:
            selected_entity_ids = {graph.entity(item).id for item in entities}
            selected_relationship_ids = {
                graph.relationship(item).id for item in relationships or ()
            }

        for relationship_id in selected_relationship_ids:
            relationship = graph.relationship(relationship_id)
            if (
                relationship.source_id not in selected_entity_ids
                or relationship.target_id not in selected_entity_ids
            ):
                raise ValueError(
                    "a View relationship cannot have an endpoint outside the View"
                )

        requested_entity_classification = graph._resolve_classification(
            entity_classification
        )
        requested_relationship_classification = graph._resolve_classification(
            relationship_classification
        )
        if requested_entity_classification is not None or predicate is not None:
            selected_entity_ids = {
                entity_id
                for entity_id in selected_entity_ids
                if graph._classification_matches(
                    graph.entity(entity_id).classification,
                    requested_entity_classification,
                )
                and (predicate is None or predicate(graph.entity(entity_id)))
            }
        selected_relationship_ids = {
            relationship_id
            for relationship_id in selected_relationship_ids
            if graph.relationship(relationship_id).source_id in selected_entity_ids
            and graph.relationship(relationship_id).target_id in selected_entity_ids
            and graph._classification_matches(
                graph.relationship(relationship_id).classification,
                requested_relationship_classification,
            )
        }
        if requested_relationship_classification is not None:
            endpoint_ids = {
                endpoint_id
                for relationship_id in selected_relationship_ids
                for endpoint_id in (
                    graph.relationship(relationship_id).source_id,
                    graph.relationship(relationship_id).target_id,
                )
            }
            selected_entity_ids.intersection_update(endpoint_ids)
            if preserve_entity_id is not None:
                selected_entity_ids.add(preserve_entity_id)
        object.__setattr__(self, "graph", graph)
        object.__setattr__(self, "_entity_ids", frozenset(selected_entity_ids))
        object.__setattr__(
            self, "_relationship_ids", frozenset(selected_relationship_ids)
        )

    @property
    def entities(self) -> tuple[Entity, ...]:
        return tuple(
            entity for entity in self.graph.entities if entity.id in self._entity_ids
        )

    @property
    def relationships(self) -> tuple[Relationship, ...]:
        return tuple(
            relationship
            for relationship in self.graph.relationships
            if relationship.id in self._relationship_ids
        )

    @property
    def roots(self) -> tuple[Entity, ...]:
        targets = {relationship.target_id for relationship in self.relationships}
        return tuple(entity for entity in self.entities if entity.id not in targets)

    @property
    def leaves(self) -> tuple[Entity, ...]:
        sources = {relationship.source_id for relationship in self.relationships}
        return tuple(entity for entity in self.entities if entity.id not in sources)

    @property
    def is_arborescence(self) -> bool:
        graph = self.to_networkx()
        return bool(graph) and nx.is_arborescence(graph)

    def filter(
        self,
        *,
        entity_classification: UUID | Classification | None = None,
        relationship_classification: UUID | Classification | None = None,
        predicate: Callable[[Entity], bool] | None = None,
    ) -> View:
        return View(
            self.graph,
            entities=self.entities,
            relationships=self.relationships,
            entity_classification=entity_classification,
            relationship_classification=relationship_classification,
            predicate=predicate,
        )

    def expand(
        self,
        via: UUID | Classification | None = None,
        *,
        outgoing: bool = True,
        incoming: bool = True,
    ) -> View:
        if not outgoing and not incoming:
            raise ValueError("expand requires outgoing or incoming relationships")
        requested = self.graph._resolve_classification(via)
        entity_ids = set(self._entity_ids)
        relationship_ids = set(self._relationship_ids)
        for edge in self.graph.relationships:
            if not self.graph._classification_matches(edge.classification, requested):
                continue
            if outgoing and edge.source_id in self._entity_ids:
                entity_ids.add(edge.target_id)
                relationship_ids.add(edge.id)
            if incoming and edge.target_id in self._entity_ids:
                entity_ids.add(edge.source_id)
                relationship_ids.add(edge.id)
        return View(
            self.graph,
            entities=entity_ids,
            relationships=relationship_ids,
        )

    def predecessors(
        self,
        entity: str | UUID | Entity,
        *,
        via: str | UUID | Classification | None = None,
    ) -> tuple[Entity, ...]:
        entity_id = self._resolve_view_entity_id(entity)
        requested = self.graph._resolve_classification(via)
        predecessor_ids = {
            edge.source_id
            for edge in self.relationships
            if edge.target_id == entity_id
            and self.graph._classification_matches(edge.classification, requested)
        }
        return tuple(item for item in self.entities if item.id in predecessor_ids)

    def successors(
        self,
        entity: str | UUID | Entity,
        *,
        via: str | UUID | Classification | None = None,
    ) -> tuple[Entity, ...]:
        entity_id = self._resolve_view_entity_id(entity)
        requested = self.graph._resolve_classification(via)
        successor_ids = {
            edge.target_id
            for edge in self.relationships
            if edge.source_id == entity_id
            and self.graph._classification_matches(edge.classification, requested)
        }
        return tuple(item for item in self.entities if item.id in successor_ids)

    def aggregate(self, reduction: Reduction[T]) -> Aggregation[T]:
        if not isinstance(reduction, Reduction):
            raise TypeError("reduction must be a Reduction")
        return reduction._execute(self)

    def to_networkx(self) -> nx.MultiDiGraph:
        return _to_networkx(self.entities, self.relationships)

    def _resolve_view_entity_id(self, entity: str | UUID | Entity) -> UUID:
        registered = self.graph.entity(entity)
        if registered.id not in self._entity_ids:
            raise MissingEntityError(registered.id)
        return registered.id
