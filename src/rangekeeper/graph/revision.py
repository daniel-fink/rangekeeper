from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from ..measure import Measure
from .characteristics import Feature, Label, Measurement
from .classification import Classification
from .entity import Entity
from .graph import Graph
from .provenance import Claim, Fact, _index_claims
from .relationship import Relationship
from .taxonomy import Taxonomy


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Modification(Generic[T]):
    before: T
    after: T


@dataclass(frozen=True, slots=True)
class ChangeSet(Generic[T]):
    added: tuple[T, ...] = ()
    removed: tuple[T, ...] = ()
    modified: tuple[Modification[T], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "added", tuple(self.added))
        object.__setattr__(self, "removed", tuple(self.removed))
        modifications = tuple(self.modified)
        if any(not isinstance(item, Modification) for item in modifications):
            raise TypeError("modified must contain only Modification objects")
        object.__setattr__(self, "modified", modifications)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.removed or self.modified)


@dataclass(frozen=True, slots=True)
class GraphDiff:
    taxonomies: ChangeSet[Taxonomy]
    classifications: ChangeSet[Classification]
    measures: ChangeSet[Measure]
    entities: ChangeSet[Entity]
    labels: ChangeSet[Label]
    measurements: ChangeSet[Measurement]
    features: ChangeSet[Feature]
    relationships: ChangeSet[Relationship]
    facts: ChangeSet[Fact[Any]]
    claims: ChangeSet[Claim[Any]]

    @property
    def changed(self) -> bool:
        return any(
            section.changed
            for section in (
                self.taxonomies,
                self.classifications,
                self.measures,
                self.entities,
                self.labels,
                self.measurements,
                self.features,
                self.relationships,
                self.facts,
                self.claims,
            )
        )

    @classmethod
    def between(cls, parent: Graph, child: Graph) -> GraphDiff:
        if not isinstance(parent, Graph) or not isinstance(child, Graph):
            raise TypeError("GraphDiff.between requires two Graph objects")
        parent_characteristics = _characteristic_items(parent)
        child_characteristics = _characteristic_items(child)
        return cls(
            taxonomies=_changes(
                {item.id: item for item in parent.definitions.taxonomies.values()},
                {item.id: item for item in child.definitions.taxonomies.values()},
            ),
            classifications=_changes(_classifications(parent), _classifications(child)),
            measures=_changes(
                {item.id: item for item in parent.definitions.measures.values()},
                {item.id: item for item in child.definitions.measures.values()},
            ),
            entities=_changes(parent._entities_by_id, child._entities_by_id),
            labels=_changes(parent_characteristics[0], child_characteristics[0]),
            measurements=_changes(parent_characteristics[1], child_characteristics[1]),
            features=_changes(parent_characteristics[2], child_characteristics[2]),
            relationships=_changes(
                parent._relationships_by_id, child._relationships_by_id
            ),
            facts=_changes(parent._facts_by_target_id, child._facts_by_target_id),
            claims=_changes(
                _index_claims(parent.provenance),
                _index_claims(child.provenance),
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphRevision:
    id: UUID = field(default_factory=uuid4)
    graph: Graph
    parent_ids: tuple[UUID, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str
    message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not isinstance(self.graph, Graph):
            raise TypeError("graph must be a Graph")
        parent_ids = tuple(self.parent_ids)
        if any(not isinstance(item, UUID) for item in parent_ids):
            raise TypeError("parent_ids must contain only UUIDs")
        if len(parent_ids) != len(set(parent_ids)):
            raise ValueError("parent_ids must be unique")
        if self.id in parent_ids:
            raise ValueError("a revision cannot be its own parent")
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if not isinstance(self.created_by, str) or not self.created_by.strip():
            raise ValueError("created_by must be a non-empty string")
        if self.message is not None and not isinstance(self.message, str):
            raise TypeError("message must be a string or None")
        object.__setattr__(self, "parent_ids", parent_ids)

    def changes_since(self, parent: GraphRevision) -> GraphDiff:
        if not isinstance(parent, GraphRevision):
            raise TypeError("parent must be a GraphRevision")
        if parent.id not in self.parent_ids:
            raise ValueError("the supplied revision is not a parent of this revision")
        return GraphDiff.between(parent.graph, self.graph)


def _changes(parent: Mapping[UUID, T], child: Mapping[UUID, T]) -> ChangeSet[T]:
    return ChangeSet(
        added=tuple(
            value for identifier, value in child.items() if identifier not in parent
        ),
        removed=tuple(
            value for identifier, value in parent.items() if identifier not in child
        ),
        modified=tuple(
            Modification(before=parent[identifier], after=value)
            for identifier, value in child.items()
            if identifier in parent and not _equal(parent[identifier], value)
        ),
    )


def _equal(left: object, right: object) -> bool:
    try:
        result = left == right
        return bool(result)
    except (TypeError, ValueError):
        return False


def _classifications(graph: Graph) -> dict[UUID, Classification]:
    return {
        item.id: item
        for taxonomy in graph.definitions.taxonomies.values()
        for item in taxonomy.classifications.values()
    }


def _characteristic_items(
    graph: Graph,
) -> tuple[dict[UUID, Label], dict[UUID, Measurement], dict[UUID, Feature]]:
    owners = (*graph.entities, *graph.relationships)
    return (
        {
            item.id: item
            for owner in owners
            for item in owner.characteristics.labels.values()
        },
        {
            item.id: item
            for owner in owners
            for item in owner.characteristics.measurements.values()
        },
        {
            item.id: item
            for owner in owners
            for item in owner.characteristics.features.values()
        },
    )
