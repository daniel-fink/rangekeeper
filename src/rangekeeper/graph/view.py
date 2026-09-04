from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

import networkx as nx

from .assembly import Assembly
from .classification import Classification
from .entity import Entity
from .errors import InvalidAggregationError, MissingEntityError
from .graph import Graph
from .reduction import Aggregation, Reduction
from .relationship import Relationship


T = TypeVar("T")

__all__ = ["View"]


@dataclass(frozen=True, init=False, slots=True)
class View:
    """A transient, immutable selection of canonical Graph membership."""

    graph: Graph
    _entity_ids: frozenset[UUID]
    _relationship_ids: frozenset[UUID]

    def __init__(
        self,
        graph: Graph,
        *,
        entities: Iterable[str | UUID | Entity] | None = None,
        relationships: Iterable[UUID | Relationship] | None = None,
        assembly: str | UUID | Assembly | None = None,
    ) -> None:
        if not isinstance(graph, Graph):
            raise TypeError("graph must be a Graph")
        if assembly is not None and (entities is not None or relationships is not None):
            raise ValueError("assembly and explicit selections are mutually exclusive")

        selected_entity_ids, selected_relationship_ids = _select(
            graph,
            entities=entities,
            relationships=relationships,
            assembly=assembly,
        )
        _validate(graph, selected_entity_ids, selected_relationship_ids)
        object.__setattr__(self, "graph", graph)
        object.__setattr__(self, "_entity_ids", frozenset(selected_entity_ids))
        object.__setattr__(
            self, "_relationship_ids", frozenset(selected_relationship_ids)
        )

    @property
    def entities(self) -> tuple[Entity, ...]:
        """Return selected entities in their Graph insertion order."""

        return tuple(
            entity for entity in self.graph.entities if entity.id in self._entity_ids
        )

    @property
    def relationships(self) -> tuple[Relationship, ...]:
        """Return selected relationships in their Graph insertion order."""

        return tuple(
            relationship
            for relationship in self.graph.relationships
            if relationship.id in self._relationship_ids
        )

    @property
    def roots(self) -> tuple[Entity, ...]:
        """Return selected entities with no incoming selected relationship."""

        targets = {relationship.target_id for relationship in self.relationships}
        return tuple(entity for entity in self.entities if entity.id not in targets)

    @property
    def leaves(self) -> tuple[Entity, ...]:
        """Return selected entities with no outgoing selected relationship."""

        sources = {relationship.source_id for relationship in self.relationships}
        return tuple(entity for entity in self.entities if entity.id not in sources)

    @property
    def is_arborescence(self) -> bool:
        """Return whether the selection is one non-empty directed tree."""

        graph = self._topology()
        return bool(graph) and nx.is_arborescence(graph)

    def filter(
        self,
        *,
        entity_classification: UUID | Classification | None = None,
        relationship_classification: UUID | Classification | None = None,
        predicate: Callable[[Entity], bool] | None = None,
    ) -> View:
        """Filter entities first, then retain relationships between survivors."""

        if predicate is not None and not callable(predicate):
            raise TypeError("predicate must be callable or None")
        entity_ids, relationship_ids = _filter(
            self.graph,
            set(self._entity_ids),
            set(self._relationship_ids),
            entity_classification=entity_classification,
            relationship_classification=relationship_classification,
            predicate=predicate,
        )
        return self._from_ids(self.graph, entity_ids, relationship_ids)

    def predecessors(
        self,
        entity: str | UUID | Entity,
        *,
        relationship_classification: UUID | Classification | None = None,
    ) -> tuple[Entity, ...]:
        """Return selected direct predecessors in entity insertion order."""

        entity_id = self._resolve_view_entity_id(entity)
        predecessor_ids = {
            edge.source_id
            for edge in self.graph.incoming_relationships(
                entity_id,
                classification=relationship_classification,
            )
            if edge.id in self._relationship_ids
        }
        return tuple(item for item in self.entities if item.id in predecessor_ids)

    def successors(
        self,
        entity: str | UUID | Entity,
        *,
        relationship_classification: UUID | Classification | None = None,
    ) -> tuple[Entity, ...]:
        """Return selected direct successors in entity insertion order."""

        entity_id = self._resolve_view_entity_id(entity)
        successor_ids = {
            edge.target_id
            for edge in self.graph.outgoing_relationships(
                entity_id,
                classification=relationship_classification,
            )
            if edge.id in self._relationship_ids
        }
        return tuple(item for item in self.entities if item.id in successor_ids)

    def aggregate(self, reduction: Reduction[T]) -> Aggregation[T]:
        """Execute a pure hierarchical reduction over this selection."""

        if not isinstance(reduction, Reduction):
            raise TypeError("reduction must be a Reduction")
        return reduction._execute(self)

    def _topology(self) -> nx.MultiDiGraph:
        """Build a frozen topology so internal algorithms cannot mutate the View."""

        graph = nx.MultiDiGraph()
        graph.add_nodes_from(
            (entity.id, {"entity": entity}) for entity in self.entities
        )
        graph.add_edges_from(
            (
                relationship.source_id,
                relationship.target_id,
                relationship.id,
                {"relationship": relationship},
            )
            for relationship in self.relationships
        )
        return nx.freeze(graph)

    def _require_arborescence(self) -> nx.MultiDiGraph:
        """Return private topology after enforcing hierarchical structure."""

        graph = self._topology()
        if not graph or not nx.is_arborescence(graph):
            raise InvalidAggregationError(
                "operation requires a non-empty parent-to-child arborescence View"
            )
        return graph

    @classmethod
    def _from_ids(
        cls,
        graph: Graph,
        entity_ids: Iterable[UUID],
        relationship_ids: Iterable[UUID],
    ) -> View:
        view = object.__new__(cls)
        object.__setattr__(view, "graph", graph)
        object.__setattr__(view, "_entity_ids", frozenset(entity_ids))
        object.__setattr__(
            view,
            "_relationship_ids",
            frozenset(relationship_ids),
        )
        return view

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
    """Resolve explicit selection modes without applying semantic filters."""

    if isinstance(entities, (str, bytes)):
        raise TypeError("entities must be an iterable of entity references")
    if isinstance(relationships, (str, bytes)):
        raise TypeError("relationships must be an iterable of relationship references")
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
    """Apply staged filters so no retained edge has a removed endpoint."""

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
