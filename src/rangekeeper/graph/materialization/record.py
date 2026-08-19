from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ..assembly import Assembly
from ..characteristics import Characteristics
from ..classification import Classification
from ..entity import Entity
from ..provenance import Provenance
from ..relationship import Relationship
from .errors import SnapshotError
from .value import encode_value


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class Record:
    record_type: str
    identifier: str
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        for value, field in (
            (self.record_type, "record_type"),
            (self.identifier, "identifier"),
        ):
            if not isinstance(value, str):
                raise TypeError(f"{field} must be a string")
            if not value.strip():
                raise ValueError(f"{field} must not be empty")
        if not isinstance(self.values, Mapping):
            raise TypeError("values must be a mapping")
        object.__setattr__(self, "values", _freeze(dict(self.values)))

    @staticmethod
    def classification_id(classification: Classification) -> str:
        if not isinstance(classification, Classification):
            raise TypeError("classification must be a Classification")
        return json.dumps(classification.key, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_classification(cls, classification: Classification) -> Record:
        return cls(
            record_type="classification",
            identifier=cls.classification_id(classification),
            values={
                "code": classification.code,
                "name": classification.name,
                "definition": classification.definition,
                "scheme": classification.scheme,
                "parent_id": (
                    cls.classification_id(classification.parent)
                    if classification.parent is not None
                    else None
                ),
            },
        )

    @classmethod
    def from_entity(cls, entity: Entity) -> Record:
        if not isinstance(entity, Entity):
            raise TypeError("entity must be an Entity")
        values = {
            "name": entity.name,
            "classification_id": (
                cls.classification_id(entity.classification)
                if entity.classification is not None
                else None
            ),
            "characteristics": _encode_characteristics(
                entity.characteristics, owner=f"entity {entity.entity_id!r}"
            ),
            "provenance": _encode_provenance(entity.provenance),
        }
        if isinstance(entity, Assembly):
            values.update(
                {
                    "entity_ids": tuple(
                        sorted(item.entity_id for item in entity.entities)
                    ),
                    "relationship_ids": tuple(
                        sorted(item.relationship_id for item in entity.relationships)
                    ),
                }
            )
        return cls(
            record_type="assembly" if isinstance(entity, Assembly) else "entity",
            identifier=entity.entity_id,
            values=values,
        )

    @classmethod
    def from_relationship(cls, relationship: Relationship) -> Record:
        if not isinstance(relationship, Relationship):
            raise TypeError("relationship must be a Relationship")
        return cls(
            record_type="relationship",
            identifier=relationship.relationship_id,
            values={
                "source_id": relationship.source_id,
                "target_id": relationship.target_id,
                "classification_id": cls.classification_id(relationship.classification),
                "characteristics": _encode_characteristics(
                    relationship.characteristics,
                    owner=f"relationship {relationship.relationship_id!r}",
                ),
                "provenance": _encode_provenance(relationship.provenance),
            },
        )


@dataclass(frozen=True)
class Snapshot:
    schema_version: int
    records: tuple[Record, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, int):
            raise TypeError("schema_version must be an integer")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        records = tuple(self.records)
        if not all(isinstance(record, Record) for record in records):
            raise TypeError("records must contain only Record instances")
        keys = [(record.record_type, record.identifier) for record in records]
        if len(keys) != len(set(keys)):
            raise ValueError("Snapshot record type/identifier pairs must be unique")
        object.__setattr__(self, "records", records)


def _encode_characteristics(
    characteristics: Characteristics,
    *,
    owner: str,
) -> dict[str, object]:
    occupancy = tuple(
        {
            "facet": facet,
            "classification_ids": tuple(
                Record.classification_id(classification)
                for classification in classifications
            ),
        }
        for facet, classifications in sorted(characteristics.occupancy.items())
    )
    measures = tuple(
        {
            "measure": encode_value(
                measure.to_record(), path=f"{owner} measure {measure.code!r}"
            ),
            "quantity": encode_value(
                quantity, path=f"{owner} measure {measure.code!r} quantity"
            ),
        }
        for measure, quantity in sorted(
            characteristics.measures.items(), key=lambda item: item[0].code
        )
    )
    if not all(isinstance(name, str) for name in characteristics.features):
        raise SnapshotError(f"{owner} feature names must be strings")
    features = tuple(
        {
            "name": name,
            "value": encode_value(value, path=f"{owner} feature {name!r}"),
        }
        for name, value in sorted(
            characteristics.features.items(), key=lambda item: item[0]
        )
    )
    return {"occupancy": occupancy, "measures": measures, "features": features}


def _encode_provenance(provenance: Provenance | None) -> object:
    if provenance is None:
        return None
    return {
        "source": provenance.source,
        "identifiers": tuple(sorted(provenance.identifiers.items())),
    }
