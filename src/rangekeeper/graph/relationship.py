from __future__ import annotations

from uuid import uuid4

from .characteristics import Characteristics
from .classification import Classification
from .provenance import Provenance


def new_relationship_id() -> str:
    return str(uuid4())


class Relationship:
    """A classified directed relationship between two stable entity IDs."""

    __slots__ = (
        "__relationship_id",
        "__source_id",
        "__target_id",
        "__classification",
        "characteristics",
        "provenance",
    )

    def __init__(
        self,
        source_id: str,
        target_id: str,
        classification: Classification,
        *,
        relationship_id: str | None = None,
        characteristics: Characteristics | None = None,
        provenance: Provenance | None = None,
    ) -> None:
        self.__relationship_id = self._validate_id(
            new_relationship_id() if relationship_id is None else relationship_id,
            "relationship_id",
        )
        self.__source_id = self._validate_id(source_id, "source_id")
        self.__target_id = self._validate_id(target_id, "target_id")
        if not isinstance(classification, Classification):
            raise TypeError("classification must be a Classification")
        self.__classification = classification
        if characteristics is None:
            characteristics = Characteristics()
        elif not isinstance(characteristics, Characteristics):
            raise TypeError("characteristics must be Characteristics or None")
        if provenance is not None and not isinstance(provenance, Provenance):
            raise TypeError("provenance must be Provenance or None")
        self.characteristics = characteristics
        self.provenance = provenance

    @staticmethod
    def _validate_id(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string")
        if not value.strip():
            raise ValueError(f"{field} must not be empty")
        return value

    @property
    def relationship_id(self) -> str:
        return self.__relationship_id

    @property
    def source_id(self) -> str:
        return self.__source_id

    @property
    def target_id(self) -> str:
        return self.__target_id

    @property
    def classification(self) -> Classification:
        return self.__classification

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Relationship):
            return NotImplemented
        return self.relationship_id == other.relationship_id

    def __hash__(self) -> int:
        return hash(self.relationship_id)

    def __repr__(self) -> str:
        return (
            f"Relationship(relationship_id={self.relationship_id!r}, "
            f"source_id={self.source_id!r}, target_id={self.target_id!r})"
        )
