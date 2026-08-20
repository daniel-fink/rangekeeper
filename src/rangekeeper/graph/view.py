from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import networkx as nx

from .assembly import Assembly
from .classification import Classification
from .entity import Entity
from .errors import MissingEntityError
from .relationship import Relationship

if TYPE_CHECKING:
    from .aggregation import AggregationCallback
    from .model import Model


@dataclass(frozen=True, init=False)
class View:
    """An immutable selection of registered Model entity and relationship IDs."""

    model: Model
    entity_ids: frozenset[str]
    relationship_ids: frozenset[str]

    def __init__(
        self,
        model: Model,
        *,
        entity_ids: Iterable[str] | None = None,
        relationship_ids: Iterable[str] | None = None,
        entity_classification: Classification | str | None = None,
        relationship_classification: Classification | str | None = None,
        assembly: Assembly | str | None = None,
        predicate: Callable[[Entity], bool] | None = None,
    ) -> None:
        from .model import Model

        if not isinstance(model, Model):
            raise TypeError("model must be a Model")
        has_entity_ids = entity_ids is not None
        has_relationship_ids = relationship_ids is not None
        if has_entity_ids != has_relationship_ids:
            raise ValueError(
                "entity_ids and relationship_ids must be supplied together"
            )
        if assembly is not None and has_entity_ids:
            raise ValueError("assembly and explicit IDs are mutually exclusive")

        preserve_entity_id: str | None = None
        if assembly is not None:
            canonical = model._resolve_assembly(assembly)
            base_entity_ids = frozenset(
                {
                    canonical.entity_id,
                    *(entity.entity_id for entity in canonical.entities),
                }
            )
            base_relationship_ids = frozenset(
                relationship.relationship_id for relationship in canonical.relationships
            )
            preserve_entity_id = canonical.entity_id
        elif has_entity_ids:
            assert entity_ids is not None
            assert relationship_ids is not None
            base_entity_ids = frozenset(entity_ids)
            base_relationship_ids = frozenset(relationship_ids)
        else:
            base_entity_ids = frozenset(model._entities)
            base_relationship_ids = frozenset(model._relationships)

        self._validate_selection(model, base_entity_ids, base_relationship_ids)
        selected_entity_ids, selected_relationship_ids = model._filter_view_ids(
            entity_ids=base_entity_ids,
            relationship_ids=base_relationship_ids,
            entity_classification=entity_classification,
            relationship_classification=relationship_classification,
            predicate=predicate,
            preserve_entity_id=preserve_entity_id,
        )
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "entity_ids", selected_entity_ids)
        object.__setattr__(self, "relationship_ids", selected_relationship_ids)

    @staticmethod
    def _validate_selection(
        model: Model,
        entity_ids: frozenset[str],
        relationship_ids: frozenset[str],
    ) -> None:
        for entity_id in entity_ids:
            model.entities[entity_id]
        for relationship_id in relationship_ids:
            relationship = model.relationships[relationship_id]
            if (
                relationship.source_id not in entity_ids
                or relationship.target_id not in entity_ids
            ):
                raise ValueError(
                    f"view relationship {relationship_id!r} has an endpoint outside the View"
                )

    def entities(self) -> tuple[Entity, ...]:
        return tuple(
            entity
            for entity in self.model.entities.all()
            if entity.entity_id in self.entity_ids
        )

    def relationships(self) -> tuple[Relationship, ...]:
        return tuple(
            relationship
            for relationship in self.model.relationships.all()
            if relationship.relationship_id in self.relationship_ids
        )

    def filter(
        self,
        *,
        entity_classification: Classification | str | None = None,
        relationship_classification: Classification | str | None = None,
        predicate: Callable[[Entity], bool] | None = None,
    ) -> View:
        return View(
            self.model,
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
        for edge in self.model.relationships.all():
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
            self.model,
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

    def aggregate(
        self,
        *,
        feature: str,
        into: str | None = None,
        reduce: AggregationCallback | None = None,
    ) -> dict[str, object]:
        """Aggregate a feature bottom-up through this parent-to-child View.

        Without ``reduce``, non-None values are added. A custom reducer receives
        the current entity and a tuple containing its own value followed by its
        child aggregates. Results remain pure unless ``into`` names a distinct
        destination feature.
        """
        from .aggregation import aggregate

        return aggregate(
            view=self,
            feature=feature,
            into=into,
            reducer=reduce,
        )

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
