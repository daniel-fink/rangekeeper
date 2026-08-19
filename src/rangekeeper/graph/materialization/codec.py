from __future__ import annotations

import json

from ..assembly import Assembly
from ..characteristics import Characteristics
from ..classification import Classification
from ..entity import Entity
from ..provenance import Provenance
from ..relationship import Relationship
from .errors import SnapshotError
from .record import Record
from .value import encode_value


def classification_identifier(classification: Classification) -> str:
    return json.dumps(classification.key, ensure_ascii=False, separators=(",", ":"))


def classification_record(classification: Classification) -> Record:
    return Record(
        record_type="classification",
        identifier=classification_identifier(classification),
        values={
            "code": classification.code,
            "name": classification.name,
            "definition": classification.definition,
            "scheme": classification.scheme,
            "parent_id": (
                classification_identifier(classification.parent)
                if classification.parent is not None
                else None
            ),
        },
    )


def entity_record(entity: Entity) -> Record:
    values = {
        "name": entity.name,
        "classification_id": (
            classification_identifier(entity.classification)
            if entity.classification is not None
            else None
        ),
        "characteristics": encode_characteristics(
            entity.characteristics, owner=f"entity {entity.entity_id!r}"
        ),
        "provenance": encode_provenance(entity.provenance),
    }
    if isinstance(entity, Assembly):
        values.update(
            {
                "entity_ids": tuple(sorted(item.entity_id for item in entity.entities)),
                "relationship_ids": tuple(
                    sorted(item.relationship_id for item in entity.relationships)
                ),
            }
        )
    return Record(
        record_type="assembly" if isinstance(entity, Assembly) else "entity",
        identifier=entity.entity_id,
        values=values,
    )


def relationship_record(relationship: Relationship) -> Record:
    return Record(
        record_type="relationship",
        identifier=relationship.relationship_id,
        values={
            "source_id": relationship.source_id,
            "target_id": relationship.target_id,
            "classification_id": classification_identifier(relationship.classification),
            "characteristics": encode_characteristics(
                relationship.characteristics,
                owner=f"relationship {relationship.relationship_id!r}",
            ),
            "provenance": encode_provenance(relationship.provenance),
        },
    )


def encode_characteristics(
    characteristics: Characteristics,
    *,
    owner: str,
) -> dict[str, object]:
    occupancy = tuple(
        {
            "facet": facet,
            "classification_ids": tuple(
                classification_identifier(classification)
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


def encode_provenance(provenance: Provenance | None) -> object:
    if provenance is None:
        return None
    return {
        "source": provenance.source,
        "identifiers": tuple(sorted(provenance.identifiers.items())),
    }
