from __future__ import annotations

import networkx as nx

from .classification import Classification


class Taxonomy:
    """A named, single-root hierarchy of Classification terms."""

    __slots__ = (
        "__code",
        "name",
        "definition",
        "_classifications",
        "_graph",
        "_frozen",
    )

    def __init__(
        self,
        code: str,
        name: str,
        definition: str | None = None,
    ) -> None:
        self.__code = self._validate_required_text(code, "code")
        self.name = self._validate_required_text(name, "name")
        if definition is not None and not isinstance(definition, str):
            raise TypeError("definition must be a string or None")
        self.definition = definition
        self._classifications: dict[str, Classification] = {}
        self._graph = nx.DiGraph()
        self._frozen = False

    @staticmethod
    def _validate_required_text(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string")
        if not value.strip():
            raise ValueError(f"{field} must not be empty")
        return value

    @property
    def code(self) -> str:
        return self.__code

    @property
    def root(self) -> Classification | None:
        if not self._classifications:
            return None
        root_code = next(
            code for code, degree in self._graph.in_degree() if degree == 0
        )
        return self._classifications[root_code]

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    def define(
        self,
        *,
        code: str,
        name: str,
        definition: str | None = None,
        parent: Classification | None = None,
    ) -> Classification:
        if self._frozen:
            raise ValueError("taxonomy is frozen")
        if code in self._classifications:
            raise ValueError(f"taxonomy already contains classification code {code!r}")
        if parent is None:
            if self._classifications:
                raise ValueError("a taxonomy can have only one root")
        else:
            self._require_member(parent)

        classification = Classification._create(
            taxonomy=self,
            code=code,
            name=name,
            definition=definition,
        )
        self._classifications[classification.code] = classification
        self._graph.add_node(classification.code)
        if parent is not None:
            self._graph.add_edge(parent.code, classification.code)
        return classification

    def classifications(self) -> tuple[Classification, ...]:
        return tuple(self._classifications.values())

    def classification(self, code: str) -> Classification:
        try:
            return self._classifications[code]
        except KeyError as error:
            raise KeyError(f"unknown classification code {code!r}") from error

    def find(self, code: str) -> Classification | None:
        if not isinstance(code, str):
            raise TypeError("code must be a string")
        return self._classifications.get(code)

    def parent(self, classification: Classification) -> Classification | None:
        self._require_member(classification)
        predecessors = tuple(self._graph.predecessors(classification.code))
        if not predecessors:
            return None
        return self._classifications[predecessors[0]]

    def children(self, classification: Classification) -> tuple[Classification, ...]:
        self._require_member(classification)
        return tuple(
            self._classifications[code]
            for code in self._graph.successors(classification.code)
        )

    def ancestors(self, classification: Classification) -> tuple[Classification, ...]:
        self._require_member(classification)
        root = self.root
        if root is None:
            return ()
        path = nx.shortest_path(self._graph, root.code, classification.code)
        return tuple(self._classifications[code] for code in path[:-1])

    def descendants(self, classification: Classification) -> tuple[Classification, ...]:
        self._require_member(classification)
        codes = tuple(nx.dfs_preorder_nodes(self._graph, classification.code))[1:]
        return tuple(self._classifications[code] for code in codes)

    def is_a(
        self,
        classification: Classification,
        ancestor: Classification,
    ) -> bool:
        if not isinstance(classification, Classification):
            raise TypeError("classification must be a Classification")
        if not isinstance(ancestor, Classification):
            raise TypeError("ancestor must be a Classification")
        if classification.taxonomy is not self or ancestor.taxonomy is not self:
            return False
        return nx.has_path(self._graph, ancestor.code, classification.code)

    def freeze(self) -> None:
        if self._frozen:
            return
        nx.freeze(self._graph)
        self._frozen = True

    def to_networkx(self) -> nx.DiGraph:
        return nx.freeze(self._graph.copy())

    def _require_member(self, classification: Classification) -> None:
        if not isinstance(classification, Classification):
            raise TypeError("classification must be a Classification")
        if classification.taxonomy is not self:
            raise ValueError("classification belongs to another Taxonomy")
        if self._classifications.get(classification.code) is not classification:
            raise ValueError("classification is not registered with this Taxonomy")

    def __repr__(self) -> str:
        return f"Taxonomy(code={self.code!r}, name={self.name!r})"
