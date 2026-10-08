"""Immutable UUID selections over canonical records in one pinned Model revision."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID
from rangekeeper.model import Model, Entity, Relationship
from rangekeeper.model.definitions import classification
from rangekeeper.model.system.errors import SelectionError, HierarchyError
from rangekeeper.model.system.membership import _assembly

if TYPE_CHECKING:
    from rangekeeper.model.system.reduction import Reduction, Aggregation


@dataclass(frozen=True, init=False)
class View:
    """Select canonical objects without copying domain state or loading integrations.

    UUID lookup is strict. Records follow Model entity encounter order (Entities
    then Assemblies) and System Relationship order, regardless of selector order.
    This presentation order gives unordered collections no mathematical meaning.
    A View need not be connected, acyclic or a tree.
    """

    __slots__ = ("model", "_entity_ids", "_relationship_ids")
    model: Model
    _entity_ids: frozenset[UUID]
    _relationship_ids: frozenset[UUID]

    def __init__(
        self,
        model: Model,
        *,
        entities: Iterable[UUID] | None = None,
        relationships: Iterable[UUID] | None = None,
        assembly: UUID | None = None,
    ) -> None:
        if not isinstance(model, Model):
            raise TypeError(
                "model must be a Model; use graph.legacy.View for old Graphs"
            )
        if isinstance(entities, (str, bytes)) or isinstance(
            relationships, (str, bytes)
        ):
            raise TypeError("selections must be iterables of UUIDs, not strings")
        if assembly is not None and (entities is not None or relationships is not None):
            raise SelectionError(
                "assembly and explicit selections are mutually exclusive"
            )
        all_edges = (model.system.relationships or ()) if model.system else ()
        if assembly is not None:
            group = _assembly(model, assembly)
            nodes = {assembly, *(group.entities or ())}
            edges = set(group.relationships or ())
        elif entities is None and relationships is None:
            nodes = {item.id for item in model.find_entities()}
            edges = {item.id for item in all_edges}
        elif relationships is None:
            nodes = {
                model.entity(id).id for id in (entities if entities is not None else ())
            }
            edges = {
                item.id
                for item in all_edges
                if item.source in nodes and item.target in nodes
            }
        else:
            edges = {model.relationship(id).id for id in relationships}
            nodes = (
                {model.entity(id).id for id in entities}
                if entities is not None
                else {
                    endpoint
                    for item in all_edges
                    if item.id in edges
                    for endpoint in (item.source, item.target)
                }
            )
        for id in edges:
            edge = model.relationship(id)
            if edge.source not in nodes or edge.target not in nodes:
                raise SelectionError(
                    f"selected Relationship {id} has an unselected endpoint"
                )
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "_entity_ids", frozenset(nodes))
        object.__setattr__(self, "_relationship_ids", frozenset(edges))

    @property
    def entities(self) -> tuple[Entity, ...]:
        """Selected canonical Entities, including separately stored Assemblies."""
        return tuple(
            item for item in self.model.find_entities() if item.id in self._entity_ids
        )

    @property
    def relationships(self) -> tuple[Relationship, ...]:
        """Selected canonical Relationships, never fabricated membership edges."""
        return (
            tuple(
                item
                for item in (self.model.system.relationships or ())
                if item.id in self._relationship_ids
            )
            if self.model.system
            else ()
        )

    def entity(self, id: UUID) -> Entity:
        """Resolve a selected Entity; known but unselected IDs raise SelectionError."""
        entity = self.model.entity(id)
        if id not in self._entity_ids:
            raise SelectionError(f"Entity {id} is outside this View of {self.model.id}")
        return entity

    def relationship(self, id: UUID) -> Relationship:
        """Resolve a selected edge, preserving the Model's missing/type errors."""
        edge = self.model.relationship(id)
        if id not in self._relationship_ids:
            raise SelectionError(
                f"Relationship {id} is outside this View of {self.model.id}"
            )
        return edge

    @property
    def roots(self) -> tuple[Entity, ...]:
        """Selected Entities with no incoming selected Relationship."""
        targets = {edge.target for edge in self.relationships}
        return tuple(item for item in self.entities if item.id not in targets)

    @property
    def leaves(self) -> tuple[Entity, ...]:
        """Selected Entities with no outgoing selected Relationship."""
        sources = {edge.source for edge in self.relationships}
        return tuple(item for item in self.entities if item.id not in sources)

    @property
    def is_arborescence(self) -> bool:
        """Whether selected Relationships form one nonempty parent-to-child tree."""
        from rangekeeper.model.system.hierarchy import Hierarchy

        try:
            Hierarchy.from_relationships(self)
        except HierarchyError:
            return False
        return True

    def filter(
        self,
        *,
        entity_classification: UUID | None = None,
        relationship_classification: UUID | None = None,
        predicate: Callable[[Entity], bool] | None = None,
    ) -> "View":
        """AND exact filters, then retain selected edges between surviving endpoints.

        Classification UUIDs must exist. Predicates return bool and remain transient
        caller operations, never serialized Model mathematics.
        """
        for id in (entity_classification, relationship_classification):
            if id is not None:
                classification(self.model.definitions, id)
        if predicate is not None and not callable(predicate):
            raise TypeError("predicate must be callable")
        nodes = set()
        for entity in self.entities:
            if (
                entity_classification is not None
                and entity.classification != entity_classification
            ):
                continue
            matches = True if predicate is None else predicate(entity)
            if not isinstance(matches, bool):
                raise TypeError("predicate must return bool")
            if matches:
                nodes.add(entity.id)
        return View(
            self.model,
            entities=nodes,
            relationships=(
                edge.id
                for edge in self.relationships
                if edge.source in nodes
                and edge.target in nodes
                and (
                    relationship_classification is None
                    or edge.classification == relationship_classification
                )
            ),
        )

    def predecessors(self, id: UUID) -> tuple[Entity, ...]:
        """Return unique direct predecessors in selected Entity order."""
        self.entity(id)
        ids = {edge.source for edge in self.relationships if edge.target == id}
        return tuple(item for item in self.entities if item.id in ids)

    def successors(self, id: UUID) -> tuple[Entity, ...]:
        """Return unique direct successors; Assembly membership is not followed."""
        self.entity(id)
        ids = {edge.target for edge in self.relationships if edge.source == id}
        return tuple(item for item in self.entities if item.id in ids)

    def aggregate(self, reduction: "Reduction") -> "Aggregation":
        """Reduce recorded quantities over this View's relationship hierarchy."""
        from rangekeeper.model.system.hierarchy import Hierarchy
        from rangekeeper.model.system.reduction import Reduction

        if not isinstance(reduction, Reduction):
            raise TypeError("reduction must be a Reduction")
        return reduction.execute(Hierarchy.from_relationships(self))


__all__ = ["View"]
