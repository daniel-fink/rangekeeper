from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

import networkx as nx

from .aggregation import AggregationFunction, aggregate_view
from .assembly import Assembly
from .characteristics import Characteristics
from .classification import Classification
from .entity import Entity
from .errors import (
    IdentityConflictError,
    InvalidAssemblyError,
    MissingEntityError,
    MissingRelationshipError,
)
from .provenance import Provenance
from .relationship import Relationship
from .validation import ValidationIssue, ValidationResult
from .view import View


if TYPE_CHECKING:
    import pint

    from .materialization.record import Snapshot


ClassificationKey = tuple[str | None, str]


class Model:
    """The validated mutation boundary for a complete domain graph."""

    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()
        self._entities: dict[str, Entity] = {}
        self._relationships: dict[str, Relationship] = {}
        self._classifications: dict[ClassificationKey, Classification] = {}

    @staticmethod
    def from_snapshot(
        snapshot: Snapshot,
        *,
        registry: pint.UnitRegistry | None = None,
    ) -> Model:
        from ..measure import Index
        from .materialization.serialization import from_snapshot as deserialize

        return deserialize(
            snapshot,
            registry=Index.registry if registry is None else registry,
        )

    def add_entity(self, entity: Entity) -> None:
        self.add_entities((entity,))

    def add_entities(self, entities: Iterable[Entity]) -> None:
        materialized = list(entities)
        supplied: dict[str, Entity] = {}
        assemblies: list[Assembly] = []
        for entity in materialized:
            if not isinstance(entity, Entity):
                raise TypeError("entities must contain only Entity instances")
            self._insert_unique_entity(supplied, entity)
            if isinstance(entity, Assembly):
                assemblies.append(entity)
        closure_entities, closure_relationships = self._collect_assembly_closure(
            assemblies
        )
        for entity in supplied.values():
            self._insert_unique_entity(closure_entities, entity)
        staged_entities, staged_relationships, staged_classifications = (
            self._stage_graph_additions(
                closure_entities.values(), closure_relationships.values()
            )
        )
        self._commit(
            staged_entities,
            staged_relationships,
            staged_classifications,
        )

    def add_relationship(self, relationship: Relationship) -> None:
        self.add_relationships((relationship,))

    def add_relationships(self, relationships: Iterable[Relationship]) -> None:
        staged_relationships = self._stage_relationships(relationships)
        self._validate_relationship_endpoints(staged_relationships.values(), set())
        staged_classifications = self._stage_classifications(
            self._relationship_classifications(staged_relationships.values())
        )
        self._commit({}, staged_relationships, staged_classifications)

    def relate(
        self,
        source: Entity | str,
        target: Entity | str,
        classification: Classification,
        *,
        characteristics: Characteristics | None = None,
        provenance: Provenance | None = None,
        relationship_id: str | None = None,
    ) -> Relationship:
        source_entity = self._resolve_entity(source)
        target_entity = self._resolve_entity(target)
        relationship = Relationship(
            source_id=source_entity.entity_id,
            target_id=target_entity.entity_id,
            classification=classification,
            relationship_id=relationship_id,
            characteristics=characteristics,
            provenance=provenance,
        )
        self.add_relationship(relationship)
        return relationship

    def add_assembly(self, assembly: Assembly) -> None:
        if not isinstance(assembly, Assembly):
            raise TypeError("assembly must be an Assembly")
        self.add_entity(assembly)

    def add_to_assembly(
        self,
        assembly: Assembly | str,
        *,
        entities: Iterable[Entity | str] = (),
        relationships: Iterable[Relationship | str] = (),
    ) -> None:
        canonical_assembly = self._resolve_assembly(assembly)
        supplied_entities = [self._resolve_or_stage_entity(item) for item in entities]
        supplied_relationships = [
            self._resolve_or_stage_relationship(item) for item in relationships
        ]
        proposed_entities, proposed_relationships = (
            canonical_assembly._prepare_contents(
                entities=(*canonical_assembly.entities, *supplied_entities),
                relationships=(
                    *canonical_assembly.relationships,
                    *supplied_relationships,
                ),
            )
        )

        closure_entities, closure_relationships = self._collect_assembly_closure(
            entity for entity in supplied_entities if isinstance(entity, Assembly)
        )
        for entity in supplied_entities:
            self._insert_unique_entity(closure_entities, entity)
        for relationship in supplied_relationships:
            self._insert_unique_relationship(closure_relationships, relationship)

        staged_entities, staged_relationships, staged_classifications = (
            self._stage_graph_additions(
                closure_entities.values(), closure_relationships.values()
            )
        )
        self._commit(
            staged_entities,
            staged_relationships,
            staged_classifications,
        )
        canonical_assembly._entities = proposed_entities
        canonical_assembly._relationships = proposed_relationships

    def remove_from_assembly(
        self,
        assembly: Assembly | str,
        *,
        entities: Iterable[Entity | str] = (),
        relationships: Iterable[Relationship | str] = (),
    ) -> None:
        canonical_assembly = self._resolve_assembly(assembly)
        removed_entities = {self._resolve_entity(item) for item in entities}
        removed_relationships = {
            self._resolve_relationship(item) for item in relationships
        }
        missing_entities = removed_entities.difference(canonical_assembly.entities)
        if missing_entities:
            missing = sorted(entity.entity_id for entity in missing_entities)
            raise InvalidAssemblyError(
                f"entities are not direct Assembly contents: {', '.join(missing)}"
            )
        missing_relationships = removed_relationships.difference(
            canonical_assembly.relationships
        )
        if missing_relationships:
            missing = sorted(
                relationship.relationship_id for relationship in missing_relationships
            )
            raise InvalidAssemblyError(
                "relationships are not direct Assembly contents: "
                f"{', '.join(missing)}"
            )

        proposed_entities, proposed_relationships = (
            canonical_assembly._prepare_contents(
                entities=canonical_assembly.entities.difference(removed_entities),
                relationships=canonical_assembly.relationships.difference(
                    removed_relationships
                ),
            )
        )
        canonical_assembly._entities = proposed_entities
        canonical_assembly._relationships = proposed_relationships

    def entity(self, entity_id: str) -> Entity:
        if not isinstance(entity_id, str):
            raise TypeError("entity_id must be a string")
        try:
            return self._entities[entity_id]
        except KeyError as error:
            raise MissingEntityError(entity_id) from error

    def relationship(self, relationship_id: str) -> Relationship:
        if not isinstance(relationship_id, str):
            raise TypeError("relationship_id must be a string")
        try:
            return self._relationships[relationship_id]
        except KeyError as error:
            raise MissingRelationshipError(relationship_id) from error

    def entities(self) -> tuple[Entity, ...]:
        return tuple(self._entities.values())

    def relationships(self) -> tuple[Relationship, ...]:
        return tuple(self._relationships.values())

    def assemblies(self) -> tuple[Assembly, ...]:
        return tuple(
            entity for entity in self._entities.values() if isinstance(entity, Assembly)
        )

    def classifications(self) -> tuple[Classification, ...]:
        return tuple(self._classifications.values())

    def assembly_entities(self, assembly: Assembly | str) -> tuple[Entity, ...]:
        canonical = self._resolve_assembly(assembly)
        return tuple(sorted(canonical.entities, key=lambda entity: entity.entity_id))

    def assembly_relationships(
        self, assembly: Assembly | str
    ) -> tuple[Relationship, ...]:
        canonical = self._resolve_assembly(assembly)
        return tuple(
            sorted(
                canonical.relationships,
                key=lambda relationship: relationship.relationship_id,
            )
        )

    def assemblies_of_entity(self, entity: Entity | str) -> tuple[Assembly, ...]:
        canonical = self._resolve_entity(entity)
        return tuple(
            assembly for assembly in self.assemblies() if canonical in assembly.entities
        )

    def assemblies_of_relationship(
        self, relationship: Relationship | str
    ) -> tuple[Assembly, ...]:
        canonical = self._resolve_relationship(relationship)
        return tuple(
            assembly
            for assembly in self.assemblies()
            if canonical in assembly.relationships
        )

    def predecessors(
        self,
        entity: Entity | str,
        relationship: Classification | str | None = None,
    ) -> tuple[Entity, ...]:
        canonical = self._resolve_entity(entity)
        return self._predecessors(
            canonical.entity_id,
            relationship,
            entity_ids=frozenset(self._entities),
            relationship_ids=frozenset(self._relationships),
        )

    def successors(
        self,
        entity: Entity | str,
        relationship: Classification | str | None = None,
    ) -> tuple[Entity, ...]:
        canonical = self._resolve_entity(entity)
        return self._successors(
            canonical.entity_id,
            relationship,
            entity_ids=frozenset(self._entities),
            relationship_ids=frozenset(self._relationships),
        )

    def view(
        self,
        *,
        entity_classification: Classification | str | None = None,
        relationship_classification: Classification | str | None = None,
        assembly: Assembly | str | None = None,
        predicate: Callable[[Entity], bool] | None = None,
    ) -> View:
        if assembly is None:
            entity_ids = frozenset(self._entities)
            relationship_ids = frozenset(self._relationships)
        else:
            canonical = self._resolve_assembly(assembly)
            entity_ids = frozenset(
                {
                    canonical.entity_id,
                    *(entity.entity_id for entity in canonical.entities),
                }
            )
            relationship_ids = frozenset(
                relationship.relationship_id for relationship in canonical.relationships
            )
        return self._filtered_view(
            entity_ids=entity_ids,
            relationship_ids=relationship_ids,
            entity_classification=entity_classification,
            relationship_classification=relationship_classification,
            predicate=predicate,
            preserve_entity_id=(
                self._resolve_assembly(assembly).entity_id
                if assembly is not None
                else None
            ),
        )

    def aggregate(
        self,
        *,
        view: View,
        feature: str,
        into: str | None = None,
        function: AggregationFunction | None = None,
        outgoing: bool = True,
    ) -> dict[str, object]:
        """Aggregate a feature bottom-up through an oriented arborescent View.

        Without ``function``, non-None numeric and Pint Quantity values are
        added. A custom function receives keyword arguments ``entity``,
        ``own_value``, and ordered ``child_values``. Results remain pure unless
        ``into`` names a distinct destination feature.
        """
        return aggregate_view(
            self,
            view=view,
            feature=feature,
            into=into,
            function=function,
            outgoing=outgoing,
        )

    def validate(self) -> ValidationResult:
        issues: list[ValidationIssue] = []

        for entity_id, entity in self._entities.items():
            if entity.entity_id != entity_id:
                self._issue(
                    issues,
                    "entity.registry_key",
                    f"entity registry key {entity_id!r} does not match its Entity ID",
                )
            if entity_id not in self._graph:
                self._issue(
                    issues,
                    "entity.node_missing",
                    f"entity {entity_id!r} has no graph node",
                )
            elif self._graph.nodes[entity_id].get("entity") is not entity:
                self._issue(
                    issues,
                    "entity.node_object",
                    f"graph node {entity_id!r} does not reference its canonical Entity",
                )
            if entity.classification is not None:
                if not isinstance(entity.classification, Classification):
                    self._issue(
                        issues,
                        "entity.classification",
                        f"entity {entity_id!r} has an invalid Classification",
                    )
                elif (
                    self._classifications.get(entity.classification.key)
                    is not entity.classification
                ):
                    self._issue(
                        issues,
                        "entity.canonical_classification",
                        f"entity {entity_id!r} has a non-canonical Classification",
                    )

        for node_id, attributes in self._graph.nodes(data=True):
            entity = attributes.get("entity")
            if not isinstance(entity, Entity):
                self._issue(
                    issues,
                    "node.entity_missing",
                    f"graph node {node_id!r} has no Entity attribute",
                )
                continue
            if node_id != entity.entity_id:
                self._issue(
                    issues,
                    "node.key",
                    f"graph node key {node_id!r} does not match Entity ID",
                )
            if self._entities.get(node_id) is not entity:
                self._issue(
                    issues,
                    "node.canonical_entity",
                    f"graph node {node_id!r} is not the registered canonical Entity",
                )

        observed_relationship_ids: set[str] = set()
        for source_id, target_id, edge_key, attributes in self._graph.edges(
            keys=True, data=True
        ):
            relationship = attributes.get("relationship")
            if not isinstance(relationship, Relationship):
                self._issue(
                    issues,
                    "edge.relationship_missing",
                    f"graph edge {edge_key!r} has no Relationship attribute",
                )
                continue
            if edge_key != relationship.relationship_id:
                self._issue(
                    issues,
                    "edge.key",
                    f"edge key {edge_key!r} does not match Relationship ID",
                )
            if edge_key in observed_relationship_ids:
                self._issue(
                    issues,
                    "edge.duplicate_key",
                    f"relationship ID {edge_key!r} is used by multiple graph edges",
                )
            observed_relationship_ids.add(edge_key)
            if (source_id, target_id) != (
                relationship.source_id,
                relationship.target_id,
            ):
                self._issue(
                    issues,
                    "edge.endpoints",
                    f"graph edge {edge_key!r} does not match Relationship endpoints",
                )
            if self._relationships.get(edge_key) is not relationship:
                self._issue(
                    issues,
                    "edge.canonical_relationship",
                    f"edge {edge_key!r} is not the canonical Relationship",
                )

        for relationship_id, relationship in self._relationships.items():
            if relationship.relationship_id != relationship_id:
                self._issue(
                    issues,
                    "relationship.registry_key",
                    f"relationship registry key {relationship_id!r} does not match its ID",
                )
            if relationship.source_id not in self._entities:
                self._issue(
                    issues,
                    "relationship.source_missing",
                    f"relationship {relationship_id!r} has a missing source endpoint",
                )
            if relationship.target_id not in self._entities:
                self._issue(
                    issues,
                    "relationship.target_missing",
                    f"relationship {relationship_id!r} has a missing target endpoint",
                )
            if not isinstance(relationship.classification, Classification):
                self._issue(
                    issues,
                    "relationship.classification",
                    f"relationship {relationship_id!r} has no valid Classification",
                )
            elif (
                self._classifications.get(relationship.classification.key)
                is not relationship.classification
            ):
                self._issue(
                    issues,
                    "relationship.canonical_classification",
                    f"relationship {relationship_id!r} has a non-canonical Classification",
                )
            if not self._graph.has_edge(
                relationship.source_id,
                relationship.target_id,
                key=relationship_id,
            ):
                self._issue(
                    issues,
                    "relationship.edge_missing",
                    f"relationship {relationship_id!r} has no matching graph edge",
                )

        for assembly in self.assemblies():
            try:
                assembly._prepare_contents(
                    entities=assembly.entities,
                    relationships=assembly.relationships,
                )
            except (TypeError, ValueError) as error:
                self._issue(
                    issues,
                    "assembly.contents",
                    f"assembly {assembly.entity_id!r}: {error}",
                )
            for entity in assembly.entities:
                if not isinstance(entity, Entity):
                    self._issue(
                        issues,
                        "assembly.entity_type",
                        f"assembly {assembly.entity_id!r} contains a non-Entity value",
                    )
                elif self._entities.get(entity.entity_id) is not entity:
                    self._issue(
                        issues,
                        "assembly.canonical_entity",
                        f"assembly {assembly.entity_id!r} contains a non-canonical Entity",
                    )
            for relationship in assembly.relationships:
                if not isinstance(relationship, Relationship):
                    self._issue(
                        issues,
                        "assembly.relationship_type",
                        f"assembly {assembly.entity_id!r} contains a non-Relationship value",
                    )
                elif (
                    self._relationships.get(relationship.relationship_id)
                    is not relationship
                ):
                    self._issue(
                        issues,
                        "assembly.canonical_relationship",
                        f"assembly {assembly.entity_id!r} contains a non-canonical Relationship",
                    )

        for key, classification in self._classifications.items():
            if not isinstance(classification, Classification):
                self._issue(
                    issues,
                    "classification.type",
                    f"classification registry entry {key!r} is not a Classification",
                )
            elif classification.key != key:
                self._issue(
                    issues,
                    "classification.registry_key",
                    f"classification registry key {key!r} does not match its Classification",
                )

        return ValidationResult(tuple(issues))

    def _stage_graph_additions(
        self,
        entities: Iterable[Entity],
        relationships: Iterable[Relationship],
    ) -> tuple[
        dict[str, Entity],
        dict[str, Relationship],
        dict[ClassificationKey, Classification],
    ]:
        staged_entities = self._stage_entities(entities)
        staged_relationships = self._stage_relationships(relationships)
        self._validate_relationship_endpoints(
            staged_relationships.values(), set(staged_entities)
        )
        staged_classifications = self._stage_classifications(
            (
                *self._entity_classifications(staged_entities.values()),
                *self._relationship_classifications(staged_relationships.values()),
            )
        )
        return staged_entities, staged_relationships, staged_classifications

    def _stage_entities(self, entities: Iterable[Entity]) -> dict[str, Entity]:
        staged: dict[str, Entity] = {}
        for entity in list(entities):
            if not isinstance(entity, Entity):
                raise TypeError("entities must contain only Entity instances")
            self._insert_unique_entity(staged, entity)
            existing = self._entities.get(entity.entity_id)
            if existing is not None and existing is not entity:
                raise IdentityConflictError(
                    f"entity_id {entity.entity_id!r} already belongs to another Entity"
                )
        return {
            entity_id: entity
            for entity_id, entity in staged.items()
            if entity_id not in self._entities
        }

    def _stage_relationships(
        self, relationships: Iterable[Relationship]
    ) -> dict[str, Relationship]:
        staged: dict[str, Relationship] = {}
        for relationship in list(relationships):
            if not isinstance(relationship, Relationship):
                raise TypeError(
                    "relationships must contain only Relationship instances"
                )
            self._insert_unique_relationship(staged, relationship)
            existing = self._relationships.get(relationship.relationship_id)
            if existing is not None and existing is not relationship:
                raise IdentityConflictError(
                    "relationship_id "
                    f"{relationship.relationship_id!r} already belongs to another Relationship"
                )
        return {
            relationship_id: relationship
            for relationship_id, relationship in staged.items()
            if relationship_id not in self._relationships
        }

    def _stage_classifications(
        self, classifications: Iterable[Classification]
    ) -> dict[ClassificationKey, Classification]:
        staged: dict[ClassificationKey, Classification] = {}
        for classification in classifications:
            root = classification.root()
            for term in (root, *root.descendants()):
                existing = staged.get(term.key) or self._classifications.get(term.key)
                if existing is not None and existing is not term:
                    raise IdentityConflictError(
                        "classification key "
                        f"{term.key!r} already belongs to another Classification"
                    )
                staged[term.key] = term
        return {
            key: classification
            for key, classification in staged.items()
            if key not in self._classifications
        }

    def _validate_relationship_endpoints(
        self,
        relationships: Iterable[Relationship],
        staged_entity_ids: set[str],
    ) -> None:
        available_ids = set(self._entities).union(staged_entity_ids)
        for relationship in relationships:
            if relationship.source_id not in available_ids:
                raise MissingEntityError(relationship.source_id)
            if relationship.target_id not in available_ids:
                raise MissingEntityError(relationship.target_id)

    def _commit(
        self,
        entities: dict[str, Entity],
        relationships: dict[str, Relationship],
        classifications: dict[ClassificationKey, Classification],
    ) -> None:
        self._classifications.update(classifications)
        for entity_id, entity in entities.items():
            self._entities[entity_id] = entity
            self._graph.add_node(entity_id, entity=entity)
        for relationship_id, relationship in relationships.items():
            self._relationships[relationship_id] = relationship
            self._graph.add_edge(
                relationship.source_id,
                relationship.target_id,
                key=relationship_id,
                relationship=relationship,
            )

    def _collect_assembly_closure(
        self, assemblies: Iterable[Assembly]
    ) -> tuple[dict[str, Entity], dict[str, Relationship]]:
        collected_entities: dict[str, Entity] = {}
        collected_relationships: dict[str, Relationship] = {}
        visited: set[str] = set()
        active: set[str] = set()

        def visit(assembly: Assembly) -> None:
            if assembly.entity_id in active:
                raise InvalidAssemblyError("assembly containment would create a cycle")
            self._insert_unique_entity(collected_entities, assembly)
            if assembly.entity_id in visited:
                return
            active.add(assembly.entity_id)
            assembly._prepare_contents(
                entities=assembly.entities,
                relationships=assembly.relationships,
            )
            for entity in sorted(assembly.entities, key=lambda item: item.entity_id):
                self._insert_unique_entity(collected_entities, entity)
                if isinstance(entity, Assembly):
                    visit(entity)
            for relationship in sorted(
                assembly.relationships,
                key=lambda item: item.relationship_id,
            ):
                self._insert_unique_relationship(collected_relationships, relationship)
            active.remove(assembly.entity_id)
            visited.add(assembly.entity_id)

        for assembly in list(assemblies):
            if not isinstance(assembly, Assembly):
                raise TypeError("assembly closure requires Assembly instances")
            visit(assembly)
        return collected_entities, collected_relationships

    @staticmethod
    def _insert_unique_entity(target: dict[str, Entity], entity: Entity) -> None:
        existing = target.get(entity.entity_id)
        if existing is not None and existing is not entity:
            raise IdentityConflictError(
                f"different Entity objects share entity_id {entity.entity_id!r}"
            )
        target[entity.entity_id] = entity

    @staticmethod
    def _insert_unique_relationship(
        target: dict[str, Relationship], relationship: Relationship
    ) -> None:
        existing = target.get(relationship.relationship_id)
        if existing is not None and existing is not relationship:
            raise IdentityConflictError(
                "different Relationship objects share relationship_id "
                f"{relationship.relationship_id!r}"
            )
        target[relationship.relationship_id] = relationship

    def _resolve_entity(self, entity: Entity | str) -> Entity:
        if isinstance(entity, str):
            return self.entity(entity)
        if not isinstance(entity, Entity):
            raise TypeError("entity must be an Entity or entity ID")
        canonical = self.entity(entity.entity_id)
        if canonical is not entity:
            raise IdentityConflictError(
                f"entity_id {entity.entity_id!r} belongs to another Entity"
            )
        return canonical

    def _resolve_or_stage_entity(self, entity: Entity | str) -> Entity:
        if isinstance(entity, str):
            return self.entity(entity)
        if not isinstance(entity, Entity):
            raise TypeError("entity must be an Entity or entity ID")
        existing = self._entities.get(entity.entity_id)
        if existing is not None and existing is not entity:
            raise IdentityConflictError(
                f"entity_id {entity.entity_id!r} belongs to another Entity"
            )
        return entity

    def _resolve_relationship(self, relationship: Relationship | str) -> Relationship:
        if isinstance(relationship, str):
            return self.relationship(relationship)
        if not isinstance(relationship, Relationship):
            raise TypeError("relationship must be a Relationship or relationship ID")
        canonical = self.relationship(relationship.relationship_id)
        if canonical is not relationship:
            raise IdentityConflictError(
                "relationship_id "
                f"{relationship.relationship_id!r} belongs to another Relationship"
            )
        return canonical

    def _resolve_or_stage_relationship(
        self, relationship: Relationship | str
    ) -> Relationship:
        if isinstance(relationship, str):
            return self.relationship(relationship)
        if not isinstance(relationship, Relationship):
            raise TypeError("relationship must be a Relationship or relationship ID")
        existing = self._relationships.get(relationship.relationship_id)
        if existing is not None and existing is not relationship:
            raise IdentityConflictError(
                "relationship_id "
                f"{relationship.relationship_id!r} belongs to another Relationship"
            )
        return relationship

    def _resolve_assembly(self, assembly: Assembly | str) -> Assembly:
        entity = self._resolve_entity(assembly)
        if not isinstance(entity, Assembly):
            raise TypeError(f"entity {entity.entity_id!r} is not an Assembly")
        return entity

    @staticmethod
    def _entity_classifications(
        entities: Iterable[Entity],
    ) -> tuple[Classification, ...]:
        classifications: list[Classification] = []
        for entity in entities:
            if entity.classification is not None:
                classifications.append(entity.classification)
            classifications.extend(
                classification
                for values in entity.occupancy.values()
                for classification in values
            )
        return tuple(classifications)

    @staticmethod
    def _relationship_classifications(
        relationships: Iterable[Relationship],
    ) -> tuple[Classification, ...]:
        classifications: list[Classification] = []
        for relationship in relationships:
            classifications.append(relationship.classification)
            classifications.extend(
                classification
                for values in relationship.characteristics.occupancy.values()
                for classification in values
            )
        return tuple(classifications)

    @staticmethod
    def _classification_matches(
        actual: Classification | None,
        requested: Classification | str | None,
    ) -> bool:
        if requested is not None and not isinstance(requested, (Classification, str)):
            raise TypeError(
                "classification filter must be a Classification, string, or None"
            )
        if requested is None:
            return True
        if actual is None:
            return False
        if isinstance(requested, Classification):
            return actual.key == requested.key
        qualified_code = (
            f"{actual.scheme}:{actual.code}"
            if actual.scheme is not None
            else actual.code
        )
        return requested in (actual.code, qualified_code)

    def _filtered_view(
        self,
        *,
        entity_ids: frozenset[str],
        relationship_ids: frozenset[str],
        entity_classification: Classification | str | None = None,
        relationship_classification: Classification | str | None = None,
        predicate: Callable[[Entity], bool] | None = None,
        preserve_entity_id: str | None = None,
    ) -> View:
        self._classification_matches(None, entity_classification)
        self._classification_matches(None, relationship_classification)
        if predicate is not None and not callable(predicate):
            raise TypeError("predicate must be callable or None")
        selected_entity_ids = {
            entity_id
            for entity_id in entity_ids
            if self._classification_matches(
                self._entities[entity_id].classification,
                entity_classification,
            )
            and (predicate is None or predicate(self._entities[entity_id]))
        }
        if (
            preserve_entity_id is not None
            and entity_classification is None
            and predicate is None
        ):
            selected_entity_ids.add(preserve_entity_id)

        selected_relationship_ids = {
            relationship_id
            for relationship_id in relationship_ids
            if self._relationships[relationship_id].source_id in selected_entity_ids
            and self._relationships[relationship_id].target_id in selected_entity_ids
            and self._classification_matches(
                self._relationships[relationship_id].classification,
                relationship_classification,
            )
        }
        if relationship_classification is not None:
            endpoint_ids = {
                endpoint_id
                for relationship_id in selected_relationship_ids
                for endpoint_id in (
                    self._relationships[relationship_id].source_id,
                    self._relationships[relationship_id].target_id,
                )
            }
            selected_entity_ids.intersection_update(endpoint_ids)
            if preserve_entity_id is not None and preserve_entity_id in entity_ids:
                selected_entity_ids.add(preserve_entity_id)

        return View(
            model=self,
            entity_ids=frozenset(selected_entity_ids),
            relationship_ids=frozenset(selected_relationship_ids),
        )

    def _predecessors(
        self,
        entity_id: str,
        relationship: Classification | str | None,
        *,
        entity_ids: frozenset[str],
        relationship_ids: frozenset[str],
    ) -> tuple[Entity, ...]:
        self._classification_matches(None, relationship)
        if entity_id not in entity_ids:
            raise MissingEntityError(entity_id)
        result: list[Entity] = []
        seen: set[str] = set()
        for edge in self._relationships.values():
            if edge.relationship_id not in relationship_ids:
                continue
            if (
                edge.target_id == entity_id
                and edge.source_id in entity_ids
                and edge.source_id not in seen
                and self._classification_matches(edge.classification, relationship)
            ):
                result.append(self._entities[edge.source_id])
                seen.add(edge.source_id)
        return tuple(result)

    def _successors(
        self,
        entity_id: str,
        relationship: Classification | str | None,
        *,
        entity_ids: frozenset[str],
        relationship_ids: frozenset[str],
    ) -> tuple[Entity, ...]:
        self._classification_matches(None, relationship)
        if entity_id not in entity_ids:
            raise MissingEntityError(entity_id)
        result: list[Entity] = []
        seen: set[str] = set()
        for edge in self._relationships.values():
            if edge.relationship_id not in relationship_ids:
                continue
            if (
                edge.source_id == entity_id
                and edge.target_id in entity_ids
                and edge.target_id not in seen
                and self._classification_matches(edge.classification, relationship)
            ):
                result.append(self._entities[edge.target_id])
                seen.add(edge.target_id)
        return tuple(result)

    @staticmethod
    def _issue(issues: list[ValidationIssue], code: str, message: str) -> None:
        issues.append(ValidationIssue(code=code, message=message))
