from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID, uuid4

import networkx as nx

from .. import validate
from ._index import Catalog
from .classification import Classification


@dataclass(frozen=True, slots=True, kw_only=True)
class Taxonomy:
    id: UUID = field(default_factory=uuid4)
    code: str
    name: str
    classifications: tuple[Classification, ...]
    definition: str | None = None
    _classification_catalog: Catalog[Classification] = field(
        init=False, repr=False, compare=False
    )
    _children_index: Mapping[UUID, tuple[UUID, ...]] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not validate.is_text(self.code):
            raise TypeError("Taxonomy.code must be a string")
        if not validate.is_text(self.code, empty=False):
            raise ValueError("Taxonomy.code must not be empty")
        if not validate.is_text(self.name):
            raise TypeError("Taxonomy.name must be a string")
        if not validate.is_text(self.name, empty=False):
            raise ValueError("Taxonomy.name must not be empty")
        if self.definition is not None and not isinstance(self.definition, str):
            raise TypeError("definition must be a string or None")
        classifications = tuple(self.classifications)
        if any(not isinstance(item, Classification) for item in classifications):
            raise TypeError("classifications must contain only Classification objects")
        catalog = Catalog(
            classifications,
            "classification",
            scope=f"taxonomy {self.code!r}",
        )
        roots = tuple(item for item in classifications if item.parent is None)
        if len(roots) != 1:
            raise ValueError("taxonomy must contain exactly one root")
        for item in classifications:
            if item.parent is None:
                continue
            if not catalog.contains_id(item.parent.id):
                raise ValueError(
                    f"classification {item.code!r} references a missing parent"
                )
            canonical_parent = catalog.by_id(item.parent.id)
            if canonical_parent is not item.parent:
                raise ValueError(
                    f"classification {item.code!r} parent is not the canonical "
                    "taxonomy object"
                )
        graph = nx.DiGraph()
        graph.add_nodes_from(item.id for item in classifications)
        graph.add_edges_from(
            (item.parent.id, item.id)
            for item in classifications
            if item.parent is not None
        )
        if not nx.is_directed_acyclic_graph(graph):
            raise ValueError("taxonomy classifications must form an acyclic hierarchy")
        object.__setattr__(self, "classifications", classifications)
        children: dict[UUID, list[UUID]] = {}
        for item in classifications:
            if item.parent is not None:
                children.setdefault(item.parent.id, []).append(item.id)
        object.__setattr__(self, "_classification_catalog", catalog)
        object.__setattr__(
            self,
            "_children_index",
            MappingProxyType(
                {
                    parent_id: tuple(child_ids)
                    for parent_id, child_ids in children.items()
                }
            ),
        )

    @property
    def root(self) -> Classification:
        return next(item for item in self.classifications if item.parent is None)

    def classification(self, reference: str | UUID | Classification) -> Classification:
        if isinstance(reference, str):
            return self._classification_catalog.by_code(reference)
        if isinstance(reference, UUID):
            warnings.warn(
                "Taxonomy.classification(UUID) is deprecated; use "
                "classification_by_id()",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.classification_by_id(reference)
        if isinstance(reference, Classification):
            warnings.warn(
                "Taxonomy.classification(Classification) is deprecated; use "
                "canonical_classification()",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.canonical_classification(reference)
        raise TypeError("classification lookup requires a code")

    def classification_by_id(self, identifier: UUID) -> Classification:
        return self._classification_catalog.by_id(identifier)

    def canonical_classification(
        self, classification: Classification
    ) -> Classification:
        if not isinstance(classification, Classification):
            raise TypeError("classification must be a Classification")
        return self._classification_catalog.canonical(classification)

    def find(self, code: str) -> Classification | None:
        return self._classification_catalog.find(code)

    def parent(
        self, classification: str | UUID | Classification
    ) -> Classification | None:
        canonical = self._resolve_classification(classification)
        return canonical.parent

    def children(
        self, classification: str | UUID | Classification
    ) -> tuple[Classification, ...]:
        canonical = self._resolve_classification(classification)
        return tuple(
            self._classification_catalog.by_id(id)
            for id in self._children_index.get(canonical.id, ())
        )

    def ancestors(
        self, classification: str | UUID | Classification
    ) -> tuple[Classification, ...]:
        current = self.parent(classification)
        result: list[Classification] = []
        while current is not None:
            result.append(current)
            current = self.parent(current)
        return tuple(reversed(result))

    def descendants(
        self, classification: str | UUID | Classification
    ) -> tuple[Classification, ...]:
        canonical = self._resolve_classification(classification)
        result: list[Classification] = []
        pending = list(self.children(canonical))
        while pending:
            item = pending.pop(0)
            result.append(item)
            pending[0:0] = self.children(item)
        return tuple(result)

    def is_a(
        self,
        classification: str | UUID | Classification,
        ancestor: str | UUID | Classification,
    ) -> bool:
        canonical = self._resolve_classification(classification)
        canonical_ancestor = self._resolve_classification(ancestor)
        return canonical == canonical_ancestor or canonical_ancestor in self.ancestors(
            canonical
        )

    def to_networkx(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        graph.add_nodes_from(
            (item.id, {"classification": item}) for item in self.classifications
        )
        graph.add_edges_from(
            (item.parent.id, item.id)
            for item in self.classifications
            if item.parent is not None
        )
        return nx.freeze(graph)

    def _resolve_classification(
        self, reference: str | UUID | Classification
    ) -> Classification:
        if isinstance(reference, str):
            return self._classification_catalog.by_code(reference)
        if isinstance(reference, UUID):
            return self.classification_by_id(reference)
        if isinstance(reference, Classification):
            return self.canonical_classification(reference)
        raise TypeError("classification reference requires a code, UUID, or object")
