from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from .. import validate
from ..measure import Measure
from .characteristics import Feature, Label, Measurement
from .classification import Classification
from .entity import Entity
from .graph import Graph
from .provenance import Claim, Fact, _claims_by_id
from .relationship import Relationship
from .taxonomy import Taxonomy


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Modification(Generic[T]):
    before: T
    after: T


@dataclass(frozen=True, slots=True)
class Delta(Generic[T]):
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
class Diff:
    taxonomies: Delta[Taxonomy]
    classifications: Delta[Classification]
    measures: Delta[Measure]
    entities: Delta[Entity]
    labels: Delta[Label]
    measurements: Delta[Measurement]
    features: Delta[Feature]
    relationships: Delta[Relationship]
    facts: Delta[Fact[Any]]
    claims: Delta[Claim[Any]]

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
    def between(cls, parent: Graph, child: Graph) -> Diff:
        if not isinstance(parent, Graph) or not isinstance(child, Graph):
            raise TypeError("Diff.between requires two Graph objects")
        parent_labels, parent_measurements, parent_features = _characteristics_by_id(
            parent
        )
        child_labels, child_measurements, child_features = _characteristics_by_id(child)
        return cls(
            taxonomies=_changes(
                {item.id: item for item in parent.definitions.taxonomies.values()},
                {item.id: item for item in child.definitions.taxonomies.values()},
            ),
            classifications=_changes(
                _classifications_by_id(parent),
                _classifications_by_id(child),
            ),
            measures=_changes(
                {item.id: item for item in parent.definitions.measures.values()},
                {item.id: item for item in child.definitions.measures.values()},
            ),
            entities=_changes(parent._entities_by_id, child._entities_by_id),
            labels=_changes(parent_labels, child_labels),
            measurements=_changes(parent_measurements, child_measurements),
            features=_changes(parent_features, child_features),
            relationships=_changes(
                parent._relationships_by_id, child._relationships_by_id
            ),
            facts=_changes(parent._facts_by_target_id, child._facts_by_target_id),
            claims=_changes(
                _claims_by_id(parent.provenance),
                _claims_by_id(child.provenance),
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Revision:
    id: UUID = field(default_factory=uuid4)
    graph: Graph
    parent_ids: tuple[UUID, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str
    message: str | None = None

    def __post_init__(self) -> None:
        validate.require_uuid(self.id, "Revision.id")
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
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        validate.require_text(self.created_by, "Revision.created_by")
        validate.optional_text(self.message, "Revision.message", empty=False)
        object.__setattr__(self, "parent_ids", parent_ids)

    def diff(self, parent: Revision) -> Diff:
        if not isinstance(parent, Revision):
            raise TypeError("parent must be a Revision")
        if parent.id not in self.parent_ids:
            raise ValueError("the supplied revision is not a parent of this revision")
        return Diff.between(parent.graph, self.graph)


def _changes(parent: Mapping[UUID, T], child: Mapping[UUID, T]) -> Delta[T]:
    return Delta(
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


def _classifications_by_id(graph: Graph) -> dict[UUID, Classification]:
    return {
        item.id: item
        for taxonomy in graph.definitions.taxonomies.values()
        for item in taxonomy.classifications.values()
    }


def _characteristics_by_id(
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
