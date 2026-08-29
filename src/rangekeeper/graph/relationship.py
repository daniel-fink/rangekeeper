from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from .characteristics import Characteristics, Feature, Label, Measurement
from .classification import Classification
from .entity import Entity


@dataclass(frozen=True, slots=True, kw_only=True)
class Relationship:
    id: UUID = field(default_factory=uuid4)
    source_id: UUID
    target_id: UUID
    classification: Classification
    characteristics: Characteristics = field(default_factory=Characteristics)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not isinstance(self.source_id, UUID):
            raise TypeError("source_id must be a UUID")
        if not isinstance(self.target_id, UUID):
            raise TypeError("target_id must be a UUID")
        if not isinstance(self.classification, Classification):
            raise TypeError("classification must be a Classification")
        if not isinstance(self.characteristics, Characteristics):
            raise TypeError("characteristics must be Characteristics")

    @property
    def labels(self) -> Mapping[str, Label]:
        return self.characteristics.labels

    @property
    def measurements(self) -> Mapping[str, Measurement]:
        return self.characteristics.measurements

    @property
    def features(self) -> Mapping[str, Feature]:
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
        if not isinstance(source, Entity) or not isinstance(target, Entity):
            raise TypeError("source and target must be Entity objects")
        if id is None:
            return cls(
                source_id=source.id,
                target_id=target.id,
                classification=classification,
                characteristics=characteristics or Characteristics(),
            )
        return cls(
            id=id,
            source_id=source.id,
            target_id=target.id,
            classification=classification,
            characteristics=characteristics or Characteristics(),
        )
