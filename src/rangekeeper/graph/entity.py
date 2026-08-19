from __future__ import annotations

from uuid import uuid4

import pint

from ..measure import Measure
from .characteristics import Characteristics
from .classification import Classification
from .provenance import Provenance


def new_entity_id() -> str:
    return str(uuid4())


class Entity:
    """A domain object with stable identity and explicit characteristics."""

    __slots__ = (
        "__entity_id",
        "name",
        "classification",
        "characteristics",
        "provenance",
    )

    def __init__(
        self,
        entity_id: str | None = None,
        name: str | None = None,
        classification: Classification | None = None,
        characteristics: Characteristics | None = None,
        provenance: Provenance | None = None,
    ) -> None:
        self.__entity_id = self._validate_id(
            new_entity_id() if entity_id is None else entity_id
        )
        if name is not None and not isinstance(name, str):
            raise TypeError("name must be a string or None")
        if classification is not None and not isinstance(
            classification, Classification
        ):
            raise TypeError("classification must be a Classification or None")
        if characteristics is None:
            characteristics = Characteristics()
        elif not isinstance(characteristics, Characteristics):
            raise TypeError("characteristics must be Characteristics or None")
        if provenance is not None and not isinstance(provenance, Provenance):
            raise TypeError("provenance must be Provenance or None")

        self.name = name
        self.classification = classification
        self.characteristics = characteristics
        self.provenance = provenance

    @staticmethod
    def _validate_id(value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("entity_id must be a string")
        if not value.strip():
            raise ValueError("entity_id must not be empty")
        return value

    @property
    def entity_id(self) -> str:
        return self.__entity_id

    @property
    def features(self) -> dict[str, object]:
        return self.characteristics.features

    @property
    def measures(self) -> dict[Measure, pint.Quantity]:
        return self.characteristics.measures

    @property
    def occupancy(self) -> dict[str, tuple[Classification, ...]]:
        return self.characteristics.occupancy

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.entity_id == other.entity_id

    def __hash__(self) -> int:
        return hash(self.entity_id)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(entity_id={self.entity_id!r}, "
            f"name={self.name!r})"
        )
