from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .taxonomy import Taxonomy


class Classification:
    """One taxonomy-owned classification term."""

    __slots__ = ("__taxonomy", "__code", "name", "definition")

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("Classifications must be defined by a Taxonomy")

    @classmethod
    def _create(
        cls,
        *,
        taxonomy: Taxonomy,
        code: str,
        name: str,
        definition: str | None,
    ) -> Classification:
        classification = object.__new__(cls)
        classification.__taxonomy = taxonomy
        classification.__code = cls._validate_required_text(code, "code")
        classification.name = cls._validate_required_text(name, "name")
        if definition is not None and not isinstance(definition, str):
            raise TypeError("definition must be a string or None")
        classification.definition = definition
        return classification

    @staticmethod
    def _validate_required_text(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string")
        if not value.strip():
            raise ValueError(f"{field} must not be empty")
        return value

    @property
    def taxonomy(self) -> Taxonomy:
        return self.__taxonomy

    @property
    def code(self) -> str:
        return self.__code

    @property
    def key(self) -> tuple[str, str]:
        return self.taxonomy.code, self.code

    @property
    def parent(self) -> Classification | None:
        return self.taxonomy.parent(self)

    @property
    def children(self) -> tuple[Classification, ...]:
        return self.taxonomy.children(self)

    def define(
        self,
        *,
        code: str,
        name: str,
        definition: str | None = None,
    ) -> Classification:
        return self.taxonomy.define(
            code=code,
            name=name,
            definition=definition,
            parent=self,
        )

    def ancestors(self) -> tuple[Classification, ...]:
        return self.taxonomy.ancestors(self)

    def descendants(self) -> tuple[Classification, ...]:
        return self.taxonomy.descendants(self)

    def lineage(self) -> tuple[Classification, ...]:
        return (*self.ancestors(), self)

    def root(self) -> Classification:
        root = self.taxonomy.root
        if root is None:
            raise RuntimeError("classification Taxonomy has no root")
        return root

    def is_a(self, ancestor: Classification) -> bool:
        return self.taxonomy.is_a(self, ancestor)

    def find(self, code: str) -> Classification | None:
        return self.taxonomy.find(code)

    def __repr__(self) -> str:
        return (
            f"Classification(taxonomy={self.taxonomy.code!r}, "
            f"code={self.code!r}, name={self.name!r})"
        )

    def __str__(self) -> str:
        return self.name
