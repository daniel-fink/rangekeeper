from __future__ import annotations

import json
from collections.abc import Iterable, Mapping

import pint

from ...measure import Index, Measure
from ..assembly import Assembly
from ..characteristics import Characteristics
from ..classification import Classification
from ..entity import Entity
from ..model import Model
from ..provenance import Provenance
from ..relationship import Relationship
from ..view import View
from .errors import SnapshotError
from .record import Record, Snapshot
from .value import decode_value, encode_value


SCHEMA_VERSION = 1
RECORD_TYPES = frozenset({"classification", "entity", "assembly", "relationship"})


def snapshot(source: Model | View) -> Snapshot:
    if isinstance(source, Model):
        model = source
        entities = model.entities()
        relationships = model.relationships()
    elif isinstance(source, View):
        model = source.model
        entities, relationships = _expand_view_references(source)
    else:
        raise TypeError("source must be a Model or View")

    classifications = _required_classifications(entities, relationships)
    records = [
        *(
            _classification_record(item)
            for item in sorted(classifications, key=classification_identifier)
        ),
        *(
            _entity_record(item)
            for item in sorted(entities, key=lambda item: item.entity_id)
        ),
        *(
            _relationship_record(item)
            for item in sorted(relationships, key=lambda item: item.relationship_id)
        ),
    ]
    return Snapshot(schema_version=SCHEMA_VERSION, records=tuple(records))


def restore(
    materialized: Snapshot,
    *,
    registry: pint.UnitRegistry = Index.registry,
) -> Model:
    if not isinstance(materialized, Snapshot):
        raise TypeError("materialized must be a Snapshot")
    if materialized.schema_version != SCHEMA_VERSION:
        raise SnapshotError(
            f"unsupported Snapshot schema version {materialized.schema_version}"
        )
    by_type: dict[str, list[Record]] = {record_type: [] for record_type in RECORD_TYPES}
    for record in materialized.records:
        if record.record_type not in RECORD_TYPES:
            raise SnapshotError(f"unknown record type {record.record_type!r}")
        by_type[record.record_type].append(record)

    classifications = _restore_classifications(by_type["classification"])
    measures: dict[str, Measure] = {}
    entities: dict[str, Entity] = {}
    assembly_records: dict[str, Record] = {}
    for record in (*by_type["entity"], *by_type["assembly"]):
        if record.identifier in entities:
            raise SnapshotError(
                f"duplicate Entity/Assembly identifier {record.identifier!r}"
            )
        values = record.values
        characteristics = _decode_characteristics(
            _mapping(values, "characteristics", record.identifier),
            classifications=classifications,
            measures=measures,
            registry=registry,
            owner=f"{record.record_type} {record.identifier!r}",
        )
        provenance = _decode_provenance(values.get("provenance"), record.identifier)
        classification = _classification_reference(
            values.get("classification_id"),
            classifications,
            owner=record.identifier,
        )
        name = values.get("name")
        if name is not None and not isinstance(name, str):
            raise SnapshotError(f"entity {record.identifier!r} name is invalid")
        entity_type = Assembly if record.record_type == "assembly" else Entity
        entity = entity_type(
            entity_id=record.identifier,
            name=name,
            classification=classification,
            characteristics=characteristics,
            provenance=provenance,
        )
        entities[record.identifier] = entity
        if isinstance(entity, Assembly):
            assembly_records[record.identifier] = record

    relationships: dict[str, Relationship] = {}
    for record in by_type["relationship"]:
        values = record.values
        source_id = _text(values, "source_id", record.identifier)
        target_id = _text(values, "target_id", record.identifier)
        for endpoint in (source_id, target_id):
            if endpoint not in entities:
                raise SnapshotError(
                    f"relationship {record.identifier!r} references missing "
                    f"Entity {endpoint!r}"
                )
        classification = _classification_reference(
            _required(values, "classification_id", record.identifier),
            classifications,
            owner=record.identifier,
            required=True,
        )
        characteristics = _decode_characteristics(
            _mapping(values, "characteristics", record.identifier),
            classifications=classifications,
            measures=measures,
            registry=registry,
            owner=f"relationship {record.identifier!r}",
        )
        relationship = Relationship(
            source_id=source_id,
            target_id=target_id,
            classification=classification,
            relationship_id=record.identifier,
            characteristics=characteristics,
            provenance=_decode_provenance(values.get("provenance"), record.identifier),
        )
        relationships[record.identifier] = relationship

    for assembly_id, record in assembly_records.items():
        assembly = entities[assembly_id]
        assert isinstance(assembly, Assembly)
        entity_ids = _text_sequence(record.values, "entity_ids", assembly_id)
        relationship_ids = _text_sequence(
            record.values, "relationship_ids", assembly_id
        )
        try:
            assembly._replace_contents(
                entities=tuple(entities[entity_id] for entity_id in entity_ids),
                relationships=tuple(
                    relationships[relationship_id]
                    for relationship_id in relationship_ids
                ),
            )
        except KeyError as error:
            raise SnapshotError(
                f"assembly {assembly_id!r} contains missing reference "
                f"{error.args[0]!r}"
            ) from error
        except (TypeError, ValueError) as error:
            raise SnapshotError(
                f"assembly {assembly_id!r} contents are invalid: {error}"
            ) from error

    model = Model()
    try:
        model.add_entities(entities.values())
        model.add_relationships(relationships.values())
    except (TypeError, ValueError, KeyError) as error:
        raise SnapshotError(f"Snapshot graph is invalid: {error}") from error
    validation = model.validate()
    if not validation:
        messages = "; ".join(issue.message for issue in validation.issues)
        raise SnapshotError(f"restored Model is invalid: {messages}")
    return model


def classification_identifier(classification: Classification) -> str:
    return json.dumps(classification.key, ensure_ascii=False, separators=(",", ":"))


def _classification_record(classification: Classification) -> Record:
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


def _entity_record(entity: Entity) -> Record:
    values = {
        "name": entity.name,
        "classification_id": (
            classification_identifier(entity.classification)
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


def _relationship_record(relationship: Relationship) -> Record:
    return Record(
        record_type="relationship",
        identifier=relationship.relationship_id,
        values={
            "source_id": relationship.source_id,
            "target_id": relationship.target_id,
            "classification_id": classification_identifier(relationship.classification),
            "characteristics": _encode_characteristics(
                relationship.characteristics,
                owner=f"relationship {relationship.relationship_id!r}",
            ),
            "provenance": _encode_provenance(relationship.provenance),
        },
    )


def _encode_characteristics(
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
    features = []
    for name, value in sorted(
        characteristics.features.items(), key=lambda item: item[0]
    ):
        features.append(
            {
                "name": name,
                "value": encode_value(value, path=f"{owner} feature {name!r}"),
            }
        )
    return {
        "occupancy": occupancy,
        "measures": measures,
        "features": tuple(features),
    }


def _decode_characteristics(
    encoded: Mapping[str, object],
    *,
    classifications: Mapping[str, Classification],
    measures: dict[str, Measure],
    registry: pint.UnitRegistry,
    owner: str,
) -> Characteristics:
    occupancy: dict[str, tuple[Classification, ...]] = {}
    for item in _mapping_sequence(encoded, "occupancy", owner):
        facet = _text(item, "facet", owner)
        ids = _text_sequence(item, "classification_ids", owner)
        occupancy[facet] = tuple(
            _classification_reference(
                identifier, classifications, owner=owner, required=True
            )
            for identifier in ids
        )

    decoded_measures: dict[Measure, pint.Quantity] = {}
    for item in _mapping_sequence(encoded, "measures", owner):
        measure_data = decode_value(
            _required(item, "measure", owner),
            registry=registry,
            path=f"{owner} measure",
        )
        if not isinstance(measure_data, Mapping):
            raise SnapshotError(f"{owner} measure definition is invalid")
        candidate = Measure.from_record(measure_data, registry=registry)
        measure = measures.get(candidate.code)
        if measure is None:
            measures[candidate.code] = candidate
            measure = candidate
        else:
            try:
                measure.assert_consistent_with(candidate)
            except ValueError as error:
                raise SnapshotError(
                    f"{owner} has conflicting Measure: {error}"
                ) from error
        quantity = decode_value(
            _required(item, "quantity", owner),
            registry=registry,
            path=f"{owner} measure {measure.code!r} quantity",
        )
        if not isinstance(quantity, pint.Quantity):
            raise SnapshotError(f"{owner} measure quantity is invalid")
        decoded_measures[measure] = quantity

    features: dict[str, object] = {}
    for item in _mapping_sequence(encoded, "features", owner):
        name = _text(item, "name", owner)
        if name in features:
            raise SnapshotError(f"{owner} contains duplicate feature {name!r}")
        features[name] = decode_value(
            _required(item, "value", owner),
            registry=registry,
            path=f"{owner} feature {name!r}",
        )
    return Characteristics(
        occupancy=occupancy,
        measures=decoded_measures,
        features=features,
    )


def _encode_provenance(provenance: Provenance | None) -> object:
    if provenance is None:
        return None
    return {
        "source": provenance.source,
        "identifiers": tuple(sorted(provenance.identifiers.items())),
    }


def _decode_provenance(value: object, owner: str) -> Provenance | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise SnapshotError(f"{owner} provenance is invalid")
    identifiers = {}
    for pair in _sequence(value, "identifiers", owner):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise SnapshotError(f"{owner} provenance identifier is invalid")
        key, identifier = pair
        if not isinstance(key, str) or not isinstance(identifier, str):
            raise SnapshotError(f"{owner} provenance identifiers must be strings")
        if key in identifiers:
            raise SnapshotError(
                f"{owner} provenance contains duplicate identifier {key!r}"
            )
        identifiers[key] = identifier
    return Provenance(source=_text(value, "source", owner), identifiers=identifiers)


def _restore_classifications(
    records: Iterable[Record],
) -> dict[str, Classification]:
    materialized = tuple(records)
    classifications: dict[str, Classification] = {}
    for record in materialized:
        values = record.values
        parent_id = values.get("parent_id")
        if parent_id is not None and not isinstance(parent_id, str):
            raise SnapshotError(
                f"classification {record.identifier!r} parent reference is invalid"
            )
        scheme = values.get("scheme")
        if scheme is not None and not isinstance(scheme, str):
            raise SnapshotError(
                f"classification {record.identifier!r} scheme is invalid"
            )
        try:
            classifications[record.identifier] = Classification(
                code=_text(values, "code", record.identifier),
                name=_text(values, "name", record.identifier),
                definition=values.get("definition"),
                scheme=scheme if parent_id is None else None,
            )
        except (TypeError, ValueError) as error:
            raise SnapshotError(
                f"classification {record.identifier!r} is invalid: {error}"
            ) from error
    try:
        for record in materialized:
            parent_id = record.values.get("parent_id")
            if parent_id is not None:
                classifications[record.identifier].set_parent(
                    classifications[parent_id]
                )
    except KeyError as error:
        raise SnapshotError(
            f"classification references missing parent {error.args[0]!r}"
        ) from error
    except (TypeError, ValueError) as error:
        raise SnapshotError(f"classification hierarchy is invalid: {error}") from error
    for record in materialized:
        classification = classifications[record.identifier]
        if classification_identifier(classification) != record.identifier:
            raise SnapshotError(
                f"classification identifier {record.identifier!r} does not match "
                "its scheme and code"
            )
    return classifications


def _required_classifications(
    entities: Iterable[Entity], relationships: Iterable[Relationship]
) -> tuple[Classification, ...]:
    by_key: dict[tuple[str | None, str], Classification] = {}

    def add(classification: Classification | None) -> None:
        if classification is None:
            return
        root = classification.root()
        for term in (root, *root.descendants()):
            existing = by_key.get(term.key)
            if existing is not None and existing is not term:
                raise SnapshotError(f"different Classifications share key {term.key!r}")
            by_key[term.key] = term

    for entity in entities:
        add(entity.classification)
        for values in entity.occupancy.values():
            for classification in values:
                add(classification)
    for relationship in relationships:
        add(relationship.classification)
        for values in relationship.characteristics.occupancy.values():
            for classification in values:
                add(classification)
    return tuple(by_key.values())


def _expand_view_references(
    view: View,
) -> tuple[tuple[Entity, ...], tuple[Relationship, ...]]:
    model = view.model
    entity_ids = set(view.entity_ids)
    relationship_ids = set(view.relationship_ids)
    pending = [
        model.entity(entity_id)
        for entity_id in entity_ids
        if isinstance(model.entity(entity_id), Assembly)
    ]
    visited: set[str] = set()
    while pending:
        assembly = pending.pop()
        assert isinstance(assembly, Assembly)
        if assembly.entity_id in visited:
            continue
        visited.add(assembly.entity_id)
        for entity in assembly.entities:
            entity_ids.add(entity.entity_id)
            if isinstance(entity, Assembly):
                pending.append(entity)
        relationship_ids.update(
            relationship.relationship_id for relationship in assembly.relationships
        )
    for relationship_id in tuple(relationship_ids):
        relationship = model.relationship(relationship_id)
        entity_ids.update((relationship.source_id, relationship.target_id))
    entities = tuple(
        entity for entity in model.entities() if entity.entity_id in entity_ids
    )
    relationships = tuple(
        relationship
        for relationship in model.relationships()
        if relationship.relationship_id in relationship_ids
    )
    return entities, relationships


def _classification_reference(
    identifier: object,
    classifications: Mapping[str, Classification],
    *,
    owner: str,
    required: bool = False,
) -> Classification | None:
    if identifier is None:
        if required:
            raise SnapshotError(f"{owner} requires a Classification reference")
        return None
    if not isinstance(identifier, str):
        raise SnapshotError(f"{owner} Classification reference is invalid")
    try:
        return classifications[identifier]
    except KeyError as error:
        raise SnapshotError(
            f"{owner} references missing Classification {identifier!r}"
        ) from error


def _required(mapping: Mapping[str, object], field: str, owner: str) -> object:
    try:
        return mapping[field]
    except KeyError as error:
        raise SnapshotError(f"{owner} is missing {field!r}") from error


def _text(mapping: Mapping[str, object], field: str, owner: str) -> str:
    value = _required(mapping, field, owner)
    if not isinstance(value, str):
        raise SnapshotError(f"{owner} field {field!r} must be a string")
    return value


def _mapping(
    mapping: Mapping[str, object], field: str, owner: str
) -> Mapping[str, object]:
    value = _required(mapping, field, owner)
    if not isinstance(value, Mapping):
        raise SnapshotError(f"{owner} field {field!r} must be a mapping")
    return value


def _sequence(
    mapping: Mapping[str, object], field: str, owner: str
) -> tuple[object, ...]:
    value = _required(mapping, field, owner)
    if not isinstance(value, (list, tuple)):
        raise SnapshotError(f"{owner} field {field!r} must be a sequence")
    return tuple(value)


def _text_sequence(
    mapping: Mapping[str, object], field: str, owner: str
) -> tuple[str, ...]:
    values = _sequence(mapping, field, owner)
    if not all(isinstance(value, str) for value in values):
        raise SnapshotError(f"{owner} field {field!r} must contain strings")
    if len(values) != len(set(values)):
        raise SnapshotError(f"{owner} field {field!r} contains duplicates")
    return values


def _mapping_sequence(
    mapping: Mapping[str, object], field: str, owner: str
) -> tuple[Mapping[str, object], ...]:
    values = _sequence(mapping, field, owner)
    if not all(isinstance(value, Mapping) for value in values):
        raise SnapshotError(f"{owner} field {field!r} must contain mappings")
    return values
