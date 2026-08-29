from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID, uuid4

import networkx as nx

from .. import validate
from ._index import Catalog, catalog_values
from .classification import Classification


@dataclass(frozen=True, slots=True, init=False)
class Taxonomy:
    id: UUID
    code: str
    name: str
    classifications: Catalog[Classification]
    definition: str | None
    _children_index: Mapping[UUID, tuple[UUID, ...]] = field(
        init=False, repr=False, compare=False
    )

    def __init__(
        self,
        *,
        code: str,
        name: str,
        classifications: Iterable[Classification] | Mapping[str, Classification],
        id: UUID | None = None,
        definition: str | None = None,
    ) -> None:
        object.__setattr__(self, "id", uuid4() if id is None else id)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "classifications", classifications)
        object.__setattr__(self, "definition", definition)
        self._validate_and_index()

    def _validate_and_index(self) -> None:
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
        classifications = catalog_values(self.classifications)
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
            if not catalog._contains_identifier(item.parent.id):
                raise ValueError(
                    f"classification {item.code!r} references a missing parent"
                )
            canonical_parent = catalog._by_identifier(item.parent.id)
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
        object.__setattr__(self, "classifications", catalog)
        children: dict[UUID, list[UUID]] = {}
        for item in classifications:
            if item.parent is not None:
                children.setdefault(item.parent.id, []).append(item.id)
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
        return next(
            item for item in self.classifications.values() if item.parent is None
        )

    def parent(self, classification: Classification) -> Classification | None:
        canonical = self._canonical(classification)
        return canonical.parent

    def children(self, classification: Classification) -> tuple[Classification, ...]:
        canonical = self._canonical(classification)
        return tuple(
            self.classifications._by_identifier(id)
            for id in self._children_index.get(canonical.id, ())
        )

    def ancestors(self, classification: Classification) -> tuple[Classification, ...]:
        current = self.parent(classification)
        result: list[Classification] = []
        while current is not None:
            result.append(current)
            current = self.parent(current)
        return tuple(reversed(result))

    def descendants(self, classification: Classification) -> tuple[Classification, ...]:
        canonical = self._canonical(classification)
        result: list[Classification] = []
        pending = list(self.children(canonical))
        while pending:
            item = pending.pop(0)
            result.append(item)
            pending[0:0] = self.children(item)
        return tuple(result)

    def is_a(
        self,
        classification: Classification,
        ancestor: Classification,
    ) -> bool:
        canonical = self._canonical(classification)
        canonical_ancestor = self._canonical(ancestor)
        return canonical == canonical_ancestor or canonical_ancestor in self.ancestors(
            canonical
        )

    def to_networkx(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        graph.add_nodes_from(
            (item.id, {"classification": item})
            for item in self.classifications.values()
        )
        graph.add_edges_from(
            (item.parent.id, item.id)
            for item in self.classifications.values()
            if item.parent is not None
        )
        return nx.freeze(graph)

    def _canonical(self, classification: Classification) -> Classification:
        if not isinstance(classification, Classification):
            raise TypeError("classification must be a Classification")
        return self.classifications._canonical(classification)
