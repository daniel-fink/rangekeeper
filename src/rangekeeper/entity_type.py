from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class EntityType:
    """A named type in a single-parent entity type hierarchy.

    Type codes are immutable and unique within a connected hierarchy. Parent and
    child mutations keep both sides of the relationship consistent.
    """

    def __init__(
        self,
        code: str,
        name: str,
        definition: str | None = None,
        *,
        parent: EntityType | None = None,
        children: Iterable[EntityType] | None = None,
    ) -> None:
        self._code = self._validate_required_text(code, "code")
        self.name = self._validate_required_text(name, "name")
        if definition is not None and not isinstance(definition, str):
            raise TypeError("definition must be a string or None")
        self.definition = definition
        self._parent: EntityType | None = None
        self._children: list[EntityType] = []

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

    @property
    def code(self) -> str:
        return self._code

    @property
    def parent(self) -> EntityType | None:
        return self._parent

    @property
    def children(self) -> tuple[EntityType, ...]:
        return tuple(self._children)

    def __repr__(self) -> str:
        return f"EntityType(code={self.code!r}, name={self.name!r})"

    def __str__(self) -> str:
        return self.name

    def set_parent(self, parent: EntityType) -> None:
        if not isinstance(parent, EntityType):
            raise TypeError("parent must be an EntityType")
        if parent is self:
            raise ValueError("an entity type cannot be its own parent")
        if parent in self.descendants():
            raise ValueError("parenting would create a cycle")
        if self._parent is parent:
            return

        subtree = set(self._walk_preorder())
        target_codes = {
            entity_type.code
            for entity_type in parent.root()._walk_preorder()
            if entity_type not in subtree
        }
        duplicate_codes = target_codes.intersection(
            entity_type.code for entity_type in subtree
        )
        if duplicate_codes:
            duplicates = ", ".join(sorted(duplicate_codes))
            raise ValueError(
                f"entity type codes must be unique within a hierarchy: {duplicates}"
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

    def add_child(self, child: EntityType) -> None:
        if not isinstance(child, EntityType):
            raise TypeError("child must be an EntityType")
        child.set_parent(self)

    def remove_child(self, child: EntityType) -> None:
        if not isinstance(child, EntityType):
            raise TypeError("child must be an EntityType")
        if child._parent is not self:
            raise ValueError("entity type is not a direct child")
        child.remove_parent()

    def add_children(self, children: Iterable[EntityType]) -> None:
        for child in children:
            self.add_child(child)

    def remove_children(self, children: Iterable[EntityType]) -> None:
        for child in children:
            self.remove_child(child)

    def define(
        self,
        *,
        code: str,
        name: str,
        definition: str | None = None,
    ) -> EntityType:
        return EntityType(
            code=code,
            name=name,
            definition=definition,
            parent=self,
        )

    def ancestors(self) -> tuple[EntityType, ...]:
        ancestors: list[EntityType] = []
        current = self._parent
        while current is not None:
            ancestors.append(current)
            current = current._parent
        ancestors.reverse()
        return tuple(ancestors)

    def descendants(self) -> tuple[EntityType, ...]:
        return tuple(self._walk_preorder())[1:]

    def lineage(self) -> tuple[EntityType, ...]:
        return (*self.ancestors(), self)

    def root(self) -> EntityType:
        current = self
        while current._parent is not None:
            current = current._parent
        return current

    def is_a(self, ancestor: EntityType) -> bool:
        if not isinstance(ancestor, EntityType):
            raise TypeError("ancestor must be an EntityType")
        return ancestor in self.lineage()

    def find(self, code: str) -> EntityType | None:
        for entity_type in self.root()._walk_preorder():
            if entity_type.code == code:
                return entity_type
        return None

    def to_record(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "name": self.name,
            "definition": self.definition,
            "parent_code": self._parent.code if self._parent is not None else None,
        }

    def to_records(self) -> tuple[dict[str, str | None], ...]:
        """Serialize the complete connected hierarchy in depth-first order."""
        return tuple(
            entity_type.to_record() for entity_type in self.root()._walk_preorder()
        )

    @classmethod
    def from_records(
        cls,
        records: Iterable[Mapping[str, Any]],
    ) -> tuple[EntityType, ...]:
        """Reconstruct one or more hierarchies and return their roots."""
        materialized = list(records)
        by_code: dict[str, EntityType] = {}

        for record in materialized:
            if not isinstance(record, Mapping):
                raise TypeError("each entity type record must be a mapping")
            try:
                code = record["code"]
                name = record["name"]
            except KeyError as error:
                raise ValueError(
                    f"entity type record is missing {error.args[0]!r}"
                ) from error
            if code in by_code:
                raise ValueError(f"duplicate entity type code: {code}")
            by_code[code] = cls(
                code=code,
                name=name,
                definition=record.get("definition"),
            )

        for record in materialized:
            parent_code = record.get("parent_code")
            if parent_code is None:
                continue
            if parent_code not in by_code:
                raise ValueError(f"unknown parent entity type code: {parent_code}")
            by_code[record["code"]].set_parent(by_code[parent_code])

        return tuple(
            entity_type
            for entity_type in by_code.values()
            if entity_type.parent is None
        )

    def _walk_preorder(self) -> Iterable[EntityType]:
        yield self
        for child in self._children:
            yield from child._walk_preorder()
