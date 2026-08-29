from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any
from uuid import UUID

import networkx as nx

from .assembly import Assembly
from ._index import index_by_id, multi_index
from .characteristics import Feature, Label, Measurement
from .classification import Classification
from .definitions import Definitions
from .entity import Entity
from .errors import (
    AmbiguousLookupError,
    IdentityConflictError,
    InvalidAssemblyError,
    MissingEntityError,
    MissingRelationshipError,
)
from .provenance import (
    Claim,
    Fact,
    FactStatus,
    SourceEdition,
    SpreadsheetLocation,
    target_value,
    values_equivalent,
)
from .relationship import Relationship

CharacteristicItem = Label | Measurement | Feature


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


@dataclass(frozen=True, slots=True)
class Graph:
    definitions: Definitions = field(default_factory=Definitions)
    entities: tuple[Entity, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    provenance: tuple[Fact[Any], ...] = ()
    _entity_store: Mapping[UUID, Entity] = field(init=False, repr=False, compare=False)
    _relationship_store: Mapping[UUID, Relationship] = field(
        init=False, repr=False, compare=False
    )
    _target_store: Mapping[UUID, Entity | Relationship | CharacteristicItem] = field(
        init=False, repr=False, compare=False
    )
    _fact_store: Mapping[UUID, Fact[Any]] = field(init=False, repr=False, compare=False)
    _claim_store: Mapping[UUID, Claim[Any]] = field(
        init=False, repr=False, compare=False
    )
    _source_edition_store: Mapping[UUID, SourceEdition] = field(
        init=False, repr=False, compare=False
    )
    _entity_code_index: Mapping[str, tuple[UUID, ...]] = field(
        init=False, repr=False, compare=False
    )
    _entity_name_index: Mapping[str, tuple[UUID, ...]] = field(
        init=False, repr=False, compare=False
    )
    _outgoing_index: Mapping[UUID, tuple[UUID, ...]] = field(
        init=False, repr=False, compare=False
    )
    _incoming_index: Mapping[UUID, tuple[UUID, ...]] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.definitions, Definitions):
            raise TypeError("definitions must be Definitions")
        entities = tuple(self.entities)
        relationships = tuple(self.relationships)
        provenance = tuple(self.provenance)
        if any(not isinstance(item, Entity) for item in entities):
            raise TypeError("entities must contain only Entity objects")
        if any(not isinstance(item, Relationship) for item in relationships):
            raise TypeError("relationships must contain only Relationship objects")
        if any(not isinstance(item, Fact) for item in provenance):
            raise TypeError("provenance must contain only Fact objects")

        entity_store = index_by_id(entities, "entity")
        relationship_store = index_by_id(relationships, "relationship")
        items: tuple[Entity | Relationship | CharacteristicItem, ...] = (
            *entities,
            *relationships,
            *(
                item
                for owner in (*entities, *relationships)
                for item in owner.characteristics.items
            ),
        )
        target_store = index_by_id(items, "graph object")
        overlap = {
            identifier
            for identifier in target_store
            if self.definitions.contains_definition_id(identifier)
        }
        if overlap:
            raise IdentityConflictError(
                f"definition and graph-object UUIDs overlap: {_format_ids(overlap)}"
            )

        self._validate_definition_references(entities, relationships)
        self._validate_relationships(relationships, entity_store)
        self._validate_assemblies(entities, relationship_store, entity_store)

        facts_by_target_id: dict[UUID, Fact[Any]] = {}
        for fact in provenance:
            target_id = fact.target.id
            if target_id in facts_by_target_id:
                raise ValueError(f"more than one Fact targets UUID {target_id}")
            canonical = target_store.get(target_id)
            if canonical is None:
                raise ValueError(
                    f"Fact targets graph object {target_id} that is not present"
                )
            if canonical is not fact.target:
                raise ValueError(
                    f"Fact target {target_id} is not the canonical graph object"
                )
            self._validate_fact_value(fact)
            facts_by_target_id[target_id] = fact
        claim_store, source_edition_store = self._index_claim_graph(provenance)

        object.__setattr__(self, "entities", entities)
        object.__setattr__(self, "relationships", relationships)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "_entity_store", entity_store)
        object.__setattr__(self, "_relationship_store", relationship_store)
        object.__setattr__(self, "_target_store", target_store)
        object.__setattr__(self, "_fact_store", MappingProxyType(facts_by_target_id))
        object.__setattr__(self, "_claim_store", claim_store)
        object.__setattr__(self, "_source_edition_store", source_edition_store)
        object.__setattr__(
            self, "_entity_code_index", multi_index(entities, lambda item: item.code)
        )
        object.__setattr__(
            self, "_entity_name_index", multi_index(entities, lambda item: item.name)
        )
        object.__setattr__(
            self,
            "_outgoing_index",
            multi_index(relationships, lambda item: item.source_id),
        )
        object.__setattr__(
            self,
            "_incoming_index",
            multi_index(relationships, lambda item: item.target_id),
        )

    @property
    def assemblies(self) -> tuple[Assembly, ...]:
        return tuple(item for item in self.entities if isinstance(item, Assembly))

    def entity(self, entity: str | UUID | Entity) -> Entity:
        if isinstance(entity, str):
            matches = self._entity_code_index.get(entity, ())
            if not matches:
                raise MissingEntityError(entity)
            if len(matches) > 1:
                raise AmbiguousLookupError(
                    f"entity code {entity!r} matches {len(matches)} entities"
                )
            entity_id = matches[0]
        else:
            entity_id = entity.id if isinstance(entity, Entity) else entity
        if not isinstance(entity_id, UUID):
            raise TypeError("entity lookup requires a code, Entity, or UUID")
        try:
            canonical = self._entity_store[entity_id]
        except KeyError as error:
            raise MissingEntityError(entity_id) from error
        if isinstance(entity, Entity) and canonical is not entity:
            raise IdentityConflictError(
                "the supplied Entity is not canonical in this Graph"
            )
        return canonical

    def relationship(self, relationship: UUID | Relationship) -> Relationship:
        relationship_id = (
            relationship.id if isinstance(relationship, Relationship) else relationship
        )
        if not isinstance(relationship_id, UUID):
            raise TypeError("relationship lookup requires a Relationship or UUID")
        try:
            canonical = self._relationship_store[relationship_id]
        except KeyError as error:
            raise MissingRelationshipError(relationship_id) from error
        if isinstance(relationship, Relationship) and canonical is not relationship:
            raise IdentityConflictError(
                "the supplied Relationship is not canonical in this Graph"
            )
        return canonical

    def fact_for(
        self, target: UUID | Entity | Relationship | CharacteristicItem
    ) -> Fact[Any] | None:
        target_id = target if isinstance(target, UUID) else target.id
        if not isinstance(target_id, UUID):
            raise TypeError("Fact lookup requires a graph object or UUID")
        return self._fact_store.get(target_id)

    def apply(self, change: GraphChange) -> Graph:
        """Validate and apply one complete change without mutating this Graph."""
        if not isinstance(change, GraphChange):
            raise TypeError("change must be a GraphChange")
        definitions = (
            self.definitions if change.definitions is None else change.definitions
        )
        entities = dict(self._entity_store)
        relationships = dict(self._relationship_store)
        facts = dict(self._fact_store)

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
                fact_removals.update(
                    item.id for item in relationship.characteristics.items
                )

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

        for id in entity_removals:
            entities.pop(id)
        for id in relationship_removals:
            relationships.pop(id)
        for id in fact_removals:
            facts.pop(id, None)

        _apply_additions(entities, change.add_entities, "entity")
        _apply_replacements(entities, change.replace_entities, "entity")
        _apply_additions(relationships, change.add_relationships, "relationship")
        _apply_replacements(relationships, change.replace_relationships, "relationship")
        _apply_fact_additions(facts, change.add_facts)
        _apply_fact_replacements(facts, change.replace_facts)

        return Graph(
            definitions=definitions,
            entities=tuple(entities.values()),
            relationships=tuple(relationships.values()),
            provenance=tuple(facts.values()),
        )

    def with_entities(self, *entities: Entity) -> Graph:
        return self.apply(GraphChange(add_entities=entities))

    def with_relationships(self, *relationships: Relationship) -> Graph:
        return self.apply(GraphChange(add_relationships=relationships))

    def with_facts(self, *facts: Fact[Any]) -> Graph:
        return self.apply(GraphChange(add_facts=facts))

    def without_entities(
        self, *entities: str | UUID | Entity, cascade: bool = False
    ) -> Graph:
        return self.apply(
            GraphChange(
                remove_entity_ids=frozenset(self.entity(item).id for item in entities),
                cascade=cascade,
            )
        )

    def without_relationships(
        self, *relationships: UUID | Relationship, cascade: bool = False
    ) -> Graph:
        return self.apply(
            GraphChange(
                remove_relationship_ids=frozenset(
                    self.relationship(item).id for item in relationships
                ),
                cascade=cascade,
            )
        )

    def find_entities(
        self,
        *,
        code: str | None = None,
        name: str | None = None,
        classification: str | UUID | Classification | None = None,
    ) -> tuple[Entity, ...]:
        for value, label in ((code, "code"), (name, "name")):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{label} must be a string or None")
        if code is not None:
            candidate_ids = set(self._entity_code_index.get(code, ()))
        elif name is not None:
            candidate_ids = set(self._entity_name_index.get(name, ()))
        else:
            candidate_ids = set(self._entity_store)
        if name is not None:
            candidate_ids.intersection_update(self._entity_name_index.get(name, ()))
        requested = self._resolve_classification(classification)
        return tuple(
            entity
            for entity in self.entities
            if entity.id in candidate_ids
            and self._classification_matches(entity.classification, requested)
        )

    def source_of(self, relationship: UUID | Relationship) -> Entity:
        return self.entity(self.relationship(relationship).source_id)

    def target_of(self, relationship: UUID | Relationship) -> Entity:
        return self.entity(self.relationship(relationship).target_id)

    def outgoing(
        self,
        entity: str | UUID | Entity,
        *,
        classification: str | UUID | Classification | None = None,
    ) -> tuple[Relationship, ...]:
        canonical = self.entity(entity)
        requested = self._resolve_classification(classification)
        relationships = tuple(
            self._relationship_store[id]
            for id in self._outgoing_index.get(canonical.id, ())
        )
        return tuple(
            relationship
            for relationship in relationships
            if self._classification_matches(relationship.classification, requested)
        )

    def incoming(
        self,
        entity: str | UUID | Entity,
        *,
        classification: str | UUID | Classification | None = None,
    ) -> tuple[Relationship, ...]:
        canonical = self.entity(entity)
        requested = self._resolve_classification(classification)
        relationships = tuple(
            self._relationship_store[id]
            for id in self._incoming_index.get(canonical.id, ())
        )
        return tuple(
            relationship
            for relationship in relationships
            if self._classification_matches(relationship.classification, requested)
        )

    def relationships_between(
        self,
        source: str | UUID | Entity,
        target: str | UUID | Entity,
        *,
        classification: str | UUID | Classification | None = None,
    ) -> tuple[Relationship, ...]:
        source_entity = self.entity(source)
        target_entity = self.entity(target)
        return tuple(
            relationship
            for relationship in self.outgoing(
                source_entity, classification=classification
            )
            if relationship.target_id == target_entity.id
        )

    def entities_in(self, assembly: str | UUID | Assembly) -> tuple[Entity, ...]:
        canonical = self.entity(assembly)
        if not isinstance(canonical, Assembly):
            raise TypeError("assembly must resolve to an Assembly")
        return tuple(
            entity for entity in self.entities if entity.id in canonical.entity_ids
        )

    def relationships_in(
        self, assembly: str | UUID | Assembly
    ) -> tuple[Relationship, ...]:
        canonical = self.entity(assembly)
        if not isinstance(canonical, Assembly):
            raise TypeError("assembly must resolve to an Assembly")
        return tuple(
            relationship
            for relationship in self.relationships
            if relationship.id in canonical.relationship_ids
        )

    def view(
        self,
        *,
        entities: Iterable[str | UUID | Entity] | None = None,
        relationships: Iterable[UUID | Relationship] | None = None,
        entity_classification: str | UUID | Classification | None = None,
        relationship_classification: str | UUID | Classification | None = None,
        assembly: str | UUID | Assembly | None = None,
        predicate: Callable[[Entity], bool] | None = None,
    ):
        from .view import View

        return View(
            self,
            entities=entities,
            relationships=relationships,
            entity_classification=entity_classification,
            relationship_classification=relationship_classification,
            assembly=assembly,
            predicate=predicate,
        )

    def to_networkx(self) -> nx.MultiDiGraph:
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

    def changes_since(self, parent: Graph):
        from .revision import GraphDiff

        return GraphDiff.between(parent, self)

    def _resolve_classification(
        self, classification: str | UUID | Classification | None
    ) -> Classification | None:
        if classification is None:
            return None
        if isinstance(classification, str):
            return self.definitions.classification(classification)
        if isinstance(classification, UUID):
            return self.definitions.classification_by_id(classification)
        if isinstance(classification, Classification):
            return self.definitions.canonical_classification(classification)
        raise TypeError("classification must be a code, UUID, Classification, or None")

    def _classification_matches(
        self,
        actual: Classification | None,
        requested: Classification | None,
    ) -> bool:
        if requested is None:
            return True
        if actual is None:
            return False
        canonical_requested = self.definitions.canonical_classification(requested)
        canonical_actual = self.definitions.canonical_classification(actual)
        try:
            taxonomy = self.definitions.taxonomy_of(canonical_actual)
        except KeyError:
            return False
        if self.definitions.taxonomy_of(canonical_requested) is not taxonomy:
            return False
        return taxonomy.is_a(canonical_actual, canonical_requested)

    def _validate_definition_references(
        self,
        entities: tuple[Entity, ...],
        relationships: tuple[Relationship, ...],
    ) -> None:
        for owner in (*entities, *relationships):
            if owner.classification is not None:
                self._require_canonical_classification(owner.classification)
            for label in owner.characteristics.labels.values():
                for classification in label.classifications:
                    self._require_canonical_classification(classification)
            for measurement in owner.characteristics.measurements.values():
                canonical = self.definitions.measure_by_id(measurement.measure.id)
                if canonical is not measurement.measure:
                    raise ValueError("measurement references a non-canonical Measure")

    def _require_canonical_classification(self, classification: Classification) -> None:
        try:
            canonical = self.definitions.classification_by_id(classification.id)
        except KeyError as error:
            raise ValueError(
                f"classification {classification.id} is not defined"
            ) from error
        if canonical is not classification:
            raise ValueError("classification reference is not canonical")

    @staticmethod
    def _validate_relationships(
        relationships: tuple[Relationship, ...],
        entities_by_id: Mapping[UUID, Entity],
    ) -> None:
        for relationship in relationships:
            if relationship.source_id not in entities_by_id:
                raise MissingEntityError(relationship.source_id)
            if relationship.target_id not in entities_by_id:
                raise MissingEntityError(relationship.target_id)

    @staticmethod
    def _validate_assemblies(
        entities: tuple[Entity, ...],
        relationships_by_id: Mapping[UUID, Relationship],
        entities_by_id: Mapping[UUID, Entity],
    ) -> None:
        assemblies = tuple(item for item in entities if isinstance(item, Assembly))
        assembly_graph = nx.DiGraph()
        assembly_graph.add_nodes_from(item.id for item in assemblies)
        for assembly in assemblies:
            missing_entities = assembly.entity_ids.difference(entities_by_id)
            missing_relationships = assembly.relationship_ids.difference(
                relationships_by_id
            )
            if missing_entities or missing_relationships:
                raise InvalidAssemblyError("assembly references missing graph members")
            allowed_endpoints = {assembly.id, *assembly.entity_ids}
            for relationship_id in assembly.relationship_ids:
                relationship = relationships_by_id[relationship_id]
                if (
                    relationship.source_id not in allowed_endpoints
                    or relationship.target_id not in allowed_endpoints
                ):
                    raise InvalidAssemblyError(
                        "assembly relationship endpoint is not a member"
                    )
            assembly_graph.add_edges_from(
                (assembly.id, member_id)
                for member_id in assembly.entity_ids
                if isinstance(entities_by_id[member_id], Assembly)
            )
        if not nx.is_directed_acyclic_graph(assembly_graph):
            raise InvalidAssemblyError("assembly membership cannot contain cycles")

    @staticmethod
    def _validate_fact_value(fact: Fact[Any]) -> None:
        if fact.status is FactStatus.CONFLICT:
            raise ValueError(
                "conflicting claims require a provisional or confirmed reconciliation"
            )
        current_claim = fact.current_claim
        if current_claim is None or not values_equivalent(
            target_value(fact.target), current_claim.value
        ):
            raise ValueError(
                "the current Fact target value does not match its selected claim"
            )

    @staticmethod
    def _index_claim_graph(
        facts: tuple[Fact[Any], ...],
    ) -> tuple[Mapping[UUID, Claim[Any]], Mapping[UUID, SourceEdition]]:
        by_id: dict[UUID, Claim[Any]] = {}
        source_editions: dict[UUID, SourceEdition] = {}
        visited: set[int] = set()
        visiting: set[int] = set()

        def visit(claim: Claim[Any]) -> None:
            identity = id(claim)
            if identity in visiting:
                raise ValueError("claim dependency graph must be acyclic")
            existing = by_id.get(claim.id)
            if existing is not None and existing is not claim:
                raise IdentityConflictError(f"different Claims share UUID {claim.id}")
            by_id[claim.id] = claim
            if identity in visited:
                return
            visiting.add(identity)
            for source in claim.sources:
                if isinstance(source, Claim):
                    visit(source)
                elif isinstance(source, SpreadsheetLocation):
                    edition = source.edition
                    prior = source_editions.get(edition.id)
                    if prior is not None and prior is not edition:
                        raise IdentityConflictError(
                            f"different SourceEditions share UUID {edition.id}"
                        )
                    source_editions[edition.id] = edition
            visiting.remove(identity)
            visited.add(identity)

        for fact in facts:
            for claim in fact.claims:
                visit(claim)
        return MappingProxyType(by_id), MappingProxyType(source_editions)


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


def _format_ids(ids: Iterable[UUID]) -> str:
    return ", ".join(str(item) for item in sorted(ids, key=str))
