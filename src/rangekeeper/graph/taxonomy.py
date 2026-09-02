from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

import networkx as nx

from .. import validate
from ._catalog import Catalog
from .classification import Classification


@dataclass(frozen=True, slots=True, init=False)
class Taxonomy:
    id: UUID
    code: str
    name: str
    classifications: Catalog[Classification]
    definition: str | None

    def __init__(
        self,
        *,
        code: str,
        name: str,
        classifications: Iterable[Classification] | Mapping[str, Classification],
        id: UUID | None = None,
        definition: str | None = None,
    ) -> None:
        identifier = uuid4() if id is None else id
        validate.require_uuid(identifier, "id")
        validate.require_text(code, "Taxonomy.code")
        validate.require_text(name, "Taxonomy.name")
        validate.optional_text(definition, "definition")
        catalog = Catalog.from_input(
            classifications,
            item_type=Classification,
            field="classifications",
            kind="classification",
            scope=f"taxonomy {code!r}",
        )

        object.__setattr__(self, "id", identifier)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "classifications", catalog)
        object.__setattr__(self, "definition", definition)
        self._validate()

    def _validate(self) -> None:
        classifications = tuple(self.classifications.values())
        roots = tuple(item for item in classifications if item.parent is None)
        if len(roots) != 1:
            raise ValueError("taxonomy must contain exactly one root")
        for item in classifications:
            if item.parent is None:
                continue
            if not self.classifications._contains_id(item.parent.id):
                raise ValueError(
                    f"classification {item.code!r} references a missing parent"
                )
            registered_parent = self.classifications._lookup_id(item.parent.id)
            if registered_parent is not item.parent:
                raise ValueError(
                    f"classification {item.code!r} parent is not the registered "
                    "taxonomy instance"
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

    @property
    def root(self) -> Classification:
        return next(
            item for item in self.classifications.values() if item.parent is None
        )

    def children(self, classification: Classification) -> tuple[Classification, ...]:
        canonical = self._require_catalog_instance(classification)
        return tuple(
            item for item in self.classifications.values() if item.parent is canonical
        )

    def ancestors(self, classification: Classification) -> tuple[Classification, ...]:
        current = self._require_catalog_instance(classification).parent
        result: list[Classification] = []
        while current is not None:
            result.append(current)
            current = current.parent
        return tuple(reversed(result))

    def descendants(self, classification: Classification) -> tuple[Classification, ...]:
        canonical = self._require_catalog_instance(classification)
        result: list[Classification] = []
        pending = list(reversed(self.children(canonical)))
        while pending:
            item = pending.pop()
            result.append(item)
            pending.extend(reversed(self.children(item)))
        return tuple(result)

    def is_a(
        self,
        classification: Classification,
        ancestor: Classification,
    ) -> bool:
        current: Classification | None = self._require_catalog_instance(classification)
        canonical_ancestor = self._require_catalog_instance(ancestor)
        while current is not None:
            if current is canonical_ancestor:
                return True
            current = current.parent
        return False

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

    def _require_catalog_instance(
        self, classification: Classification
    ) -> Classification:
        if not isinstance(classification, Classification):
            raise TypeError("classification must be a Classification")
        return self.classifications._require_catalog_instance(classification)
