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
        if assembly is not None and any(
            value is not None
            for value in (
                entities,
                relationships,
                entity_classification,
                relationship_classification,
                predicate,
            )
        ):
            raise ValueError(
                "assembly and selections or filters are mutually exclusive"
            )
        if predicate is not None and not callable(predicate):
            raise TypeError("predicate must be callable or None")

        selected_entity_ids, selected_relationship_ids = _select(
            graph,
            entities=entities,
            relationships=relationships,
            assembly=assembly,
        )
        _validate(graph, selected_entity_ids, selected_relationship_ids)
        selected_entity_ids, selected_relationship_ids = _filter(
            graph,
            selected_entity_ids,
            selected_relationship_ids,
            entity_classification=entity_classification,
            relationship_classification=relationship_classification,
            predicate=predicate,
        )
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

    def predecessors(
        self,
        entity: str | UUID | Entity,
        *,
        via: UUID | Classification | None = None,
    ) -> tuple[Entity, ...]:
        entity_id = self._resolve_view_entity_id(entity)
        predecessor_ids = {
            edge.source_id
            for edge in self.graph.incoming(entity_id, classification=via)
            if edge.id in self._relationship_ids
        }
        return tuple(item for item in self.entities if item.id in predecessor_ids)

    def successors(
        self,
        entity: str | UUID | Entity,
        *,
        via: UUID | Classification | None = None,
    ) -> tuple[Entity, ...]:
        entity_id = self._resolve_view_entity_id(entity)
        successor_ids = {
            edge.target_id
            for edge in self.graph.outgoing(entity_id, classification=via)
            if edge.id in self._relationship_ids
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


def _select(
    graph: Graph,
    *,
    entities: Iterable[str | UUID | Entity] | None,
    relationships: Iterable[UUID | Relationship] | None,
    assembly: str | UUID | Assembly | None,
) -> tuple[set[UUID], set[UUID]]:
    if assembly is not None:
        candidate = graph.entity(assembly)
        if not isinstance(candidate, Assembly):
            raise TypeError("assembly must resolve to an Assembly")
        return (
            {candidate.id, *candidate.entity_ids},
            set(candidate.relationship_ids),
        )
    if entities is None and relationships is None:
        return set(graph._entities_by_id), set(graph._relationships_by_id)
    if entities is not None and relationships is None:
        entity_ids = {graph.entity(item).id for item in entities}
        relationship_ids = {
            relationship.id
            for relationship in graph.relationships
            if relationship.source_id in entity_ids
            and relationship.target_id in entity_ids
        }
        return entity_ids, relationship_ids
    if entities is None:
        relationship_ids = {graph.relationship(item).id for item in relationships or ()}
        entity_ids = {
            endpoint
            for identifier in relationship_ids
            for endpoint in (
                graph._relationships_by_id[identifier].source_id,
                graph._relationships_by_id[identifier].target_id,
            )
        }
        return entity_ids, relationship_ids
    return (
        {graph.entity(item).id for item in entities},
        {graph.relationship(item).id for item in relationships or ()},
    )


def _filter(
    graph: Graph,
    entity_ids: set[UUID],
    relationship_ids: set[UUID],
    *,
    entity_classification: UUID | Classification | None,
    relationship_classification: UUID | Classification | None,
    predicate: Callable[[Entity], bool] | None,
) -> tuple[set[UUID], set[UUID]]:
    requested_entity_classification = graph.definitions._resolve_classification(
        entity_classification
    )
    requested_relationship_classification = graph.definitions._resolve_classification(
        relationship_classification
    )
    if requested_entity_classification is not None or predicate is not None:
        entity_ids = {
            identifier
            for identifier in entity_ids
            if graph.definitions._classification_matches(
                graph._entities_by_id[identifier].classification,
                requested_entity_classification,
            )
            and (predicate is None or predicate(graph._entities_by_id[identifier]))
        }
    relationship_ids = {
        identifier
        for identifier in relationship_ids
        if graph._relationships_by_id[identifier].source_id in entity_ids
        and graph._relationships_by_id[identifier].target_id in entity_ids
        and graph.definitions._classification_matches(
            graph._relationships_by_id[identifier].classification,
            requested_relationship_classification,
        )
    }
    if requested_relationship_classification is not None:
        endpoint_ids = {
            endpoint
            for identifier in relationship_ids
            for endpoint in (
                graph._relationships_by_id[identifier].source_id,
                graph._relationships_by_id[identifier].target_id,
            )
        }
        entity_ids.intersection_update(endpoint_ids)
    return entity_ids, relationship_ids


def _validate(
    graph: Graph,
    entity_ids: set[UUID],
    relationship_ids: set[UUID],
) -> None:
    for identifier in relationship_ids:
        relationship = graph._relationships_by_id[identifier]
        if (
            relationship.source_id not in entity_ids
            or relationship.target_id not in entity_ids
        ):
            raise ValueError(
                "a View relationship cannot have an endpoint outside the View"
            )
