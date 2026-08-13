from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class Kind:
    """A named classification in a single-parent kind hierarchy.

    Kind codes are immutable and unique within a connected hierarchy. Parent and
    child mutations keep both sides of the relationship consistent. Optional
    classification provenance belongs to a hierarchy root and is inherited by
    its descendants.
    """

    def __init__(
        self,
        code: str,
        name: str,
        definition: str | None = None,
        *,
        scheme: str | None = None,
        edition: str | None = None,
        publisher: str | None = None,
        uri: str | None = None,
        parent: Kind | None = None,
        children: Iterable[Kind] | None = None,
    ) -> None:
        self._code = self._validate_required_text(code, "code")
        self.name = self._validate_required_text(name, "name")
        if definition is not None and not isinstance(definition, str):
            raise TypeError("definition must be a string or None")
        self.definition = definition
        self._scheme = self._validate_optional_text(scheme, "scheme")
        self._edition = self._validate_optional_text(edition, "edition")
        self._publisher = self._validate_optional_text(publisher, "publisher")
        self._uri = self._validate_optional_text(uri, "uri")
        if self._scheme is None and self._has_provenance_metadata():
            raise ValueError(
                "scheme is required when classification provenance is provided"
            )
        self._parent: Kind | None = None
        self._children: list[Kind] = []

        if parent is not None:
            self.set_parent(parent)
        if children is not None:
            self.add_children(children)

    @staticmethod
    def _validate_required_text(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string")
        if not value.strip():
            raise ValueError(f"{field} must not be empty")
        return value

    @staticmethod
    def _validate_optional_text(value: str | None, field: str) -> str | None:
        if value is None:
            return None
        return Kind._validate_required_text(value, field)

    @property
    def code(self) -> str:
        return self._code

    @property
    def scheme(self) -> str | None:
        return self.root()._scheme

    @property
    def edition(self) -> str | None:
        return self.root()._edition

    @property
    def publisher(self) -> str | None:
        return self.root()._publisher

    @property
    def uri(self) -> str | None:
        return self.root()._uri

    @property
    def parent(self) -> Kind | None:
        return self._parent

    @property
    def children(self) -> tuple[Kind, ...]:
        return tuple(self._children)

    def __repr__(self) -> str:
        return f"Kind(code={self.code!r}, name={self.name!r})"

    def __str__(self) -> str:
        return self.name

    def set_parent(self, parent: Kind) -> None:
        if not isinstance(parent, Kind):
            raise TypeError("parent must be a Kind")
        if parent is self:
            raise ValueError("a kind cannot be its own parent")
        if parent in self.descendants():
            raise ValueError("parenting would create a cycle")
        if self._parent is parent:
            return
        if self._scheme is not None:
            raise ValueError("a kind with classification provenance must remain a root")

        subtree = set(self._walk_preorder())
        target_codes = {
            kind.code for kind in parent.root()._walk_preorder() if kind not in subtree
        }
        duplicate_codes = target_codes.intersection(kind.code for kind in subtree)
        if duplicate_codes:
            duplicates = ", ".join(sorted(duplicate_codes))
            raise ValueError(
                f"kind codes must be unique within a hierarchy: {duplicates}"
            )

        previous_parent = self._parent
        if previous_parent is not None:
            previous_parent._children.remove(self)
        self._parent = parent
        parent._children.append(self)

    def remove_parent(self) -> None:
        if self._parent is None:
            return
        parent = self._parent
        self._parent = None
        parent._children.remove(self)

    def add_child(self, child: Kind) -> None:
        if not isinstance(child, Kind):
            raise TypeError("child must be a Kind")
        child.set_parent(self)

    def remove_child(self, child: Kind) -> None:
        if not isinstance(child, Kind):
            raise TypeError("child must be a Kind")
        if child._parent is not self:
            raise ValueError("kind is not a direct child")
        child.remove_parent()

    def add_children(self, children: Iterable[Kind]) -> None:
        for child in children:
            self.add_child(child)

    def remove_children(self, children: Iterable[Kind]) -> None:
        for child in children:
            self.remove_child(child)

    def define(
        self,
        *,
        code: str,
        name: str,
        definition: str | None = None,
    ) -> Kind:
        return Kind(
            code=code,
            name=name,
            definition=definition,
            parent=self,
        )

    def ancestors(self) -> tuple[Kind, ...]:
        ancestors: list[Kind] = []
        current = self._parent
        while current is not None:
            ancestors.append(current)
            current = current._parent
        ancestors.reverse()
        return tuple(ancestors)

    def descendants(self) -> tuple[Kind, ...]:
        return tuple(self._walk_preorder())[1:]

    def lineage(self) -> tuple[Kind, ...]:
        return (*self.ancestors(), self)

    def root(self) -> Kind:
        current = self
        while current._parent is not None:
            current = current._parent
        return current

    def is_a(self, ancestor: Kind) -> bool:
        if not isinstance(ancestor, Kind):
            raise TypeError("ancestor must be a Kind")
        return ancestor in self.lineage()

    def find(self, code: str) -> Kind | None:
        for kind in self.root()._walk_preorder():
            if kind.code == code:
                return kind
        return None

    def to_record(self) -> dict[str, str | None]:
        record = {
            "code": self.code,
            "name": self.name,
            "definition": self.definition,
            "parent_code": self._parent.code if self._parent is not None else None,
        }
        if self._parent is None and self._scheme is not None:
            record.update(
                {
                    "scheme": self._scheme,
                    "edition": self._edition,
                    "publisher": self._publisher,
                    "uri": self._uri,
                }
            )
        return record

    def to_records(self) -> tuple[dict[str, str | None], ...]:
        """Serialize the complete connected hierarchy in depth-first order."""
        return tuple(kind.to_record() for kind in self.root()._walk_preorder())

    @classmethod
    def from_records(
        cls,
        records: Iterable[Mapping[str, Any]],
    ) -> tuple[Kind, ...]:
        """Reconstruct one or more hierarchies and return their roots."""
        materialized = list(records)
        by_code: dict[str, Kind] = {}

        for record in materialized:
            if not isinstance(record, Mapping):
                raise TypeError("each kind record must be a mapping")
            try:
                code = record["code"]
                name = record["name"]
            except KeyError as error:
                raise ValueError(f"kind record is missing {error.args[0]!r}") from error
            if code in by_code:
                raise ValueError(f"duplicate kind code: {code}")
            by_code[code] = cls(
                code=code,
                name=name,
                definition=record.get("definition"),
                scheme=record.get("scheme"),
                edition=record.get("edition"),
                publisher=record.get("publisher"),
                uri=record.get("uri"),
            )

        for record in materialized:
            parent_code = record.get("parent_code")
            if parent_code is None:
                continue
            if parent_code not in by_code:
                raise ValueError(f"unknown parent kind code: {parent_code}")
            by_code[record["code"]].set_parent(by_code[parent_code])

        return tuple(kind for kind in by_code.values() if kind.parent is None)

    def _walk_preorder(self) -> Iterable[Kind]:
        yield self
        for child in self._children:
            yield from child._walk_preorder()

    def _has_provenance_metadata(self) -> bool:
        return any(
            value is not None for value in (self._edition, self._publisher, self._uri)
        )
