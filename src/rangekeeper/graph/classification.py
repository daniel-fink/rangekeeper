from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class Classification:
    """One term in a single-parent classification hierarchy."""

    def __init__(
        self,
        code: str,
        name: str,
        definition: str | None = None,
        *,
        scheme: str | None = None,
        parent: Classification | None = None,
        children: Iterable[Classification] | None = None,
    ) -> None:
        self._code = self._validate_required_text(code, "code")
        self.name = self._validate_required_text(name, "name")
        if definition is not None and not isinstance(definition, str):
            raise TypeError("definition must be a string or None")
        self.definition = definition
        self._scheme = self._validate_optional_text(scheme, "scheme")
        self._parent: Classification | None = None
        self._children: list[Classification] = []

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
        return Classification._validate_required_text(value, field)

    @property
    def code(self) -> str:
        return self._code

    @property
    def scheme(self) -> str | None:
        return self.root()._scheme

    @property
    def key(self) -> tuple[str | None, str]:
        """Return the scheme-aware key used by registries and adapters."""
        return self.scheme, self.code

    @property
    def parent(self) -> Classification | None:
        return self._parent

    @property
    def children(self) -> tuple[Classification, ...]:
        return tuple(self._children)

    def __repr__(self) -> str:
        return f"Classification(code={self.code!r}, name={self.name!r})"

    def __str__(self) -> str:
        return self.name

    def set_parent(self, parent: Classification) -> None:
        if not isinstance(parent, Classification):
            raise TypeError("parent must be a Classification")
        if parent is self:
            raise ValueError("a classification cannot be its own parent")
        if parent in self.descendants():
            raise ValueError("parenting would create a cycle")
        if self._parent is parent:
            return
        if self._scheme is not None:
            raise ValueError(
                "a classification with scheme provenance must remain a root"
            )

        subtree = set(self._traverse())
        target_codes = {
            classification.code
            for classification in parent.root()._traverse()
            if classification not in subtree
        }
        duplicate_codes = target_codes.intersection(
            classification.code for classification in subtree
        )
        if duplicate_codes:
            duplicates = ", ".join(sorted(duplicate_codes))
            raise ValueError(
                "classification codes must be unique within a hierarchy: "
                f"{duplicates}"
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

    def add_child(self, child: Classification) -> None:
        if not isinstance(child, Classification):
            raise TypeError("child must be a Classification")
        child.set_parent(self)

    def remove_child(self, child: Classification) -> None:
        if not isinstance(child, Classification):
            raise TypeError("child must be a Classification")
        if child._parent is not self:
            raise ValueError("classification is not a direct child")
        child.remove_parent()

    def add_children(self, children: Iterable[Classification]) -> None:
        for child in children:
            self.add_child(child)

    def remove_children(self, children: Iterable[Classification]) -> None:
        for child in children:
            self.remove_child(child)

    def define(
        self,
        *,
        code: str,
        name: str,
        definition: str | None = None,
    ) -> Classification:
        return Classification(
            code=code,
            name=name,
            definition=definition,
            parent=self,
        )

    def ancestors(self) -> tuple[Classification, ...]:
        ancestors: list[Classification] = []
        current = self._parent
        while current is not None:
            ancestors.append(current)
            current = current._parent
        ancestors.reverse()
        return tuple(ancestors)

    def descendants(self) -> tuple[Classification, ...]:
        return tuple(self._traverse())[1:]

    def lineage(self) -> tuple[Classification, ...]:
        return (*self.ancestors(), self)

    def root(self) -> Classification:
        current = self
        while current._parent is not None:
            current = current._parent
        return current

    def is_a(self, ancestor: Classification) -> bool:
        if not isinstance(ancestor, Classification):
            raise TypeError("ancestor must be a Classification")
        return ancestor in self.lineage()

    def find(self, code: str) -> Classification | None:
        for classification in self.root()._traverse():
            if classification.code == code:
                return classification
        return None

    def to_record(self) -> dict[str, str | None]:
        record = {
            "code": self.code,
            "name": self.name,
            "definition": self.definition,
            "parent_code": self._parent.code if self._parent is not None else None,
        }
        if self._parent is None and self._scheme is not None:
            record["scheme"] = self._scheme
        return record

    def to_records(self) -> tuple[dict[str, str | None], ...]:
        """Serialize the complete connected hierarchy in depth-first order."""
        return tuple(
            classification.to_record() for classification in self.root()._traverse()
        )

    @classmethod
    def from_records(
        cls,
        records: Iterable[Mapping[str, Any]],
    ) -> tuple[Classification, ...]:
        """Reconstruct one or more hierarchies and return their roots."""
        materialized = list(records)
        by_code: dict[str, Classification] = {}

        for record in materialized:
            if not isinstance(record, Mapping):
                raise TypeError("each classification record must be a mapping")
            try:
                code = record["code"]
                name = record["name"]
            except KeyError as error:
                raise ValueError(
                    f"classification record is missing {error.args[0]!r}"
                ) from error
            if code in by_code:
                raise ValueError(f"duplicate classification code: {code}")
            by_code[code] = cls(
                code=code,
                name=name,
                definition=record.get("definition"),
                scheme=record.get("scheme"),
            )

        for record in materialized:
            parent_code = record.get("parent_code")
            if parent_code is None:
                continue
            if parent_code not in by_code:
                raise ValueError(f"unknown parent classification code: {parent_code}")
            by_code[record["code"]].set_parent(by_code[parent_code])

        return tuple(
            classification
            for classification in by_code.values()
            if classification.parent is None
        )

    def _traverse(self) -> Iterable[Classification]:
        yield self
        for child in self._children:
            yield from child._traverse()
