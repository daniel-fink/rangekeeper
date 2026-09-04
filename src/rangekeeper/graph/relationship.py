from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from .. import validate
from .characteristics import Characteristics, Feature, Label, Measurement
from .classification import Classification
from .entity import Entity


__all__ = ["Relationship"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Relationship:
    """A classified directed edge between two canonical entity UUIDs."""

    id: UUID = field(default_factory=uuid4)
    source_id: UUID
    target_id: UUID
    classification: Classification
    characteristics: Characteristics = field(default_factory=Characteristics)

    def __post_init__(self) -> None:
        validate.require_uuid(self.id, "Relationship.id")
        validate.require_uuid(self.source_id, "Relationship.source_id")
        validate.require_uuid(self.target_id, "Relationship.target_id")
        if not isinstance(self.classification, Classification):
            raise TypeError("classification must be a Classification")
        if not isinstance(self.characteristics, Characteristics):
            raise TypeError("characteristics must be Characteristics")

    @property
    def labels(self) -> Mapping[str, Label]:
        """Expose the relationship's immutable labels mapping."""

        return self.characteristics.labels

    @property
    def measurements(self) -> Mapping[str, Measurement]:
        """Expose the relationship's immutable measurements mapping."""

        return self.characteristics.measurements

    @property
    def features(self) -> Mapping[str, Feature]:
        """Expose the relationship's immutable features mapping."""

        return self.characteristics.features

    @classmethod
    def between(
        cls,
        source: Entity,
        target: Entity,
        *,
        classification: Classification,
        characteristics: Characteristics | None = None,
        id: UUID | None = None,
    ) -> Relationship:
        """Create a relationship from entities while storing only their UUIDs."""

        if not isinstance(source, Entity) or not isinstance(target, Entity):
            raise TypeError("source and target must be Entity objects")
        return cls(
            id=uuid4() if id is None else id,
            source_id=source.id,
            target_id=target.id,
            classification=classification,
            characteristics=(
                Characteristics() if characteristics is None else characteristics
            ),
        )
