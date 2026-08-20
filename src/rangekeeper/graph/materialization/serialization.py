from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import pint

from ...measure import Measure
from ..assembly import Assembly
from ..characteristics import Characteristics
from ..classification import Classification
from ..entity import Entity
from ..model import Model
from ..provenance import Provenance
from ..relationship import Relationship
from ..view import View
from . import value as encoded_value
from .errors import SnapshotError
from .fields import Fields
from .record import Record, Snapshot


SCHEMA_VERSION = 1
RECORD_TYPES = frozenset({"classification", "entity", "assembly", "relationship"})


def to_snapshot(source: Model | View) -> Snapshot:
    entities, relationships = _graph_closure(source)
    classifications = _classification_closure(entities, relationships)
    records = (
        *(
            Record.from_classification(item)
            for item in sorted(classifications, key=Record.classification_id)
        ),
        *(
            Record.from_entity(item)
            for item in sorted(entities, key=lambda item: item.entity_id)
        ),
        *(
            Record.from_relationship(item)
            for item in sorted(relationships, key=lambda item: item.relationship_id)
        ),
    )
    return Snapshot(schema_version=SCHEMA_VERSION, records=records)


def _graph_closure(
    source: Model | View,
) -> tuple[tuple[Entity, ...], tuple[Relationship, ...]]:
    if isinstance(source, Model):
        return source.entities(), source.relationships()
    if not isinstance(source, View):
        raise TypeError("source must be a Model or View")

    model = source.model
    entity_ids: set[str] = set()
    relationship_ids: set[str] = set()
    pending_entities = list(source.entity_ids)
    pending_relationships = list(source.relationship_ids)

    while pending_entities or pending_relationships:
        if pending_entities:
            entity_id = pending_entities.pop()
            if entity_id in entity_ids:
                continue
            entity_ids.add(entity_id)
            entity = model.entity(entity_id)
            if isinstance(entity, Assembly):
                pending_entities.extend(item.entity_id for item in entity.entities)
                pending_relationships.extend(
                    item.relationship_id for item in entity.relationships
                )
            continue

        relationship_id = pending_relationships.pop()
        if relationship_id in relationship_ids:
            continue
        relationship_ids.add(relationship_id)
        relationship = model.relationship(relationship_id)
        pending_entities.extend((relationship.source_id, relationship.target_id))

    return (
        tuple(entity for entity in model.entities() if entity.entity_id in entity_ids),
        tuple(
            relationship
            for relationship in model.relationships()
            if relationship.relationship_id in relationship_ids
        ),
    )


def _classification_closure(
    entities: Iterable[Entity],
    relationships: Iterable[Relationship],
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
        for classifications in entity.occupancy.values():
            for classification in classifications:
                add(classification)
    for relationship in relationships:
        add(relationship.classification)
        for classifications in relationship.characteristics.occupancy.values():
            for classification in classifications:
                add(classification)
    return tuple(by_key.values())


def from_snapshot(
    snapshot: Snapshot,
    *,
    registry: pint.UnitRegistry,
) -> Model:
    if not isinstance(snapshot, Snapshot):
        raise TypeError("snapshot must be a Snapshot")
    if snapshot.schema_version != SCHEMA_VERSION:
        raise SnapshotError(
            f"unsupported Snapshot schema version {snapshot.schema_version}"
        )
    return _Deserializer(registry).to_model(snapshot.records)


@dataclass
class _Deserializer:
    registry: pint.UnitRegistry
    classifications: dict[str, Classification] = field(default_factory=dict)
    measures: dict[str, Measure] = field(default_factory=dict)
    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    assembly_records: dict[str, Record] = field(default_factory=dict)

    def to_model(self, records: Iterable[Record]) -> Model:
        by_type = self._partition(records)
        self._load_classifications(by_type["classification"])
        for record in (*by_type["entity"], *by_type["assembly"]):
            self._add_entity(record)
        for record in by_type["relationship"]:
            self._add_relationship(record)
        self._populate_assemblies()
        return self._build_model()

    @staticmethod
    def _partition(records: Iterable[Record]) -> dict[str, list[Record]]:
        by_type: dict[str, list[Record]] = {
            record_type: [] for record_type in RECORD_TYPES
        }
        for record in records:
            try:
                by_type[record.record_type].append(record)
            except KeyError as error:
                raise SnapshotError(
                    f"unknown record type {record.record_type!r}"
                ) from error
        return by_type

    def _load_classifications(self, records: Iterable[Record]) -> None:
        materialized = tuple(records)
        for record in materialized:
            fields = Fields(record.values, f"classification {record.identifier!r}")
            parent_id = fields.get("parent_id")
            if parent_id is not None and not isinstance(parent_id, str):
                raise SnapshotError(f"{fields.owner} parent reference is invalid")
            scheme = fields.get("scheme")
            if scheme is not None and not isinstance(scheme, str):
                raise SnapshotError(f"{fields.owner} scheme is invalid")
            try:
                self.classifications[record.identifier] = Classification(
                    code=fields.text("code"),
                    name=fields.text("name"),
                    definition=fields.get("definition"),
                    scheme=scheme if parent_id is None else None,
                )
            except (TypeError, ValueError) as error:
                raise SnapshotError(f"{fields.owner} is invalid: {error}") from error

        try:
            for record in materialized:
                parent_id = record.values.get("parent_id")
                if parent_id is not None:
                    self.classifications[record.identifier].set_parent(
                        self.classifications[parent_id]
                    )
        except KeyError as error:
            raise SnapshotError(
                f"classification references missing parent {error.args[0]!r}"
            ) from error
        except (TypeError, ValueError) as error:
            raise SnapshotError(
                f"classification hierarchy is invalid: {error}"
            ) from error

        for record in materialized:
            classification = self.classifications[record.identifier]
            if Record.classification_id(classification) != record.identifier:
                raise SnapshotError(
                    f"classification identifier {record.identifier!r} does not "
                    "match its scheme and code"
                )

    def _add_entity(self, record: Record) -> None:
        if record.identifier in self.entities:
            raise SnapshotError(
                f"duplicate Entity/Assembly identifier {record.identifier!r}"
            )
        fields = Fields(record.values, f"{record.record_type} {record.identifier!r}")
        name = fields.get("name")
        if name is not None and not isinstance(name, str):
            raise SnapshotError(f"{fields.owner} name is invalid")
        entity_type = Assembly if record.record_type == "assembly" else Entity
        entity = entity_type(
            entity_id=record.identifier,
            name=name,
            classification=self._classification(
                fields.get("classification_id"), owner=fields.owner
            ),
            characteristics=self._characteristics(
                fields.mapping("characteristics"), owner=fields.owner
            ),
            provenance=self._provenance(fields.get("provenance"), owner=fields.owner),
        )
        self.entities[record.identifier] = entity
        if isinstance(entity, Assembly):
            self.assembly_records[record.identifier] = record

    def _add_relationship(self, record: Record) -> None:
        fields = Fields(record.values, f"relationship {record.identifier!r}")
        source_id = fields.text("source_id")
        target_id = fields.text("target_id")
        for endpoint in (source_id, target_id):
            if endpoint not in self.entities:
                raise SnapshotError(
                    f"{fields.owner} references missing Entity {endpoint!r}"
                )
        classification = self._classification(
            fields.required("classification_id"),
            owner=fields.owner,
            required=True,
        )
        assert classification is not None
        self.relationships[record.identifier] = Relationship(
            source_id=source_id,
            target_id=target_id,
            classification=classification,
            relationship_id=record.identifier,
            characteristics=self._characteristics(
                fields.mapping("characteristics"), owner=fields.owner
            ),
            provenance=self._provenance(fields.get("provenance"), owner=fields.owner),
        )

    def _populate_assemblies(self) -> None:
        for assembly_id, record in self.assembly_records.items():
            assembly = self.entities[assembly_id]
            assert isinstance(assembly, Assembly)
            fields = Fields(record.values, f"assembly {assembly_id!r}")
            entity_ids = fields.texts("entity_ids", unique=True)
            relationship_ids = fields.texts("relationship_ids", unique=True)
            try:
                assembly._replace_contents(
                    entities=tuple(self.entities[item] for item in entity_ids),
                    relationships=tuple(
                        self.relationships[item] for item in relationship_ids
                    ),
                )
            except KeyError as error:
                raise SnapshotError(
                    f"{fields.owner} contains missing reference {error.args[0]!r}"
                ) from error
            except (TypeError, ValueError) as error:
                raise SnapshotError(
                    f"{fields.owner} contents are invalid: {error}"
                ) from error

    def _build_model(self) -> Model:
        model = Model()
        try:
            model.add_entities(self.entities.values())
            model.add_relationships(self.relationships.values())
        except (TypeError, ValueError, KeyError) as error:
            raise SnapshotError(f"Snapshot graph is invalid: {error}") from error
        validation = model.validate()
        if not validation:
            messages = "; ".join(issue.message for issue in validation.issues)
            raise SnapshotError(f"restored Model is invalid: {messages}")
        return model

    def _classification(
        self,
        identifier: object,
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
            return self.classifications[identifier]
        except KeyError as error:
            raise SnapshotError(
                f"{owner} references missing Classification {identifier!r}"
            ) from error

    def _characteristics(
        self, encoded: Mapping[str, object], *, owner: str
    ) -> Characteristics:
        fields = Fields(encoded, owner)
        occupancy: dict[str, tuple[Classification, ...]] = {}
        for item in fields.mappings("occupancy"):
            item_fields = Fields(item, owner)
            facet = item_fields.text("facet")
            if facet in occupancy:
                raise SnapshotError(
                    f"{owner} contains duplicate occupancy facet {facet!r}"
                )
            values = tuple(
                self._classification(identifier, owner=owner, required=True)
                for identifier in item_fields.texts("classification_ids", unique=True)
            )
            assert all(value is not None for value in values)
            occupancy[facet] = values

        decoded_measures: dict[Measure, pint.Quantity] = {}
        for item in fields.mappings("measures"):
            item_fields = Fields(item, owner)
            measure_data = encoded_value.decode(
                item_fields.required("measure"),
                registry=self.registry,
                path=f"{owner} measure",
            )
            if not isinstance(measure_data, Mapping):
                raise SnapshotError(f"{owner} measure definition is invalid")
            try:
                candidate = Measure.from_record(measure_data, registry=self.registry)
            except (TypeError, ValueError, pint.errors.PintError) as error:
                raise SnapshotError(f"{owner} Measure is invalid: {error}") from error
            measure = self.measures.get(candidate.code)
            if measure is None:
                self.measures[candidate.code] = candidate
                measure = candidate
            else:
                try:
                    measure.assert_consistent_with(candidate)
                except ValueError as error:
                    raise SnapshotError(
                        f"{owner} has conflicting Measure: {error}"
                    ) from error
            if measure in decoded_measures:
                raise SnapshotError(
                    f"{owner} contains duplicate Measure {measure.code!r}"
                )
            quantity = encoded_value.decode(
                item_fields.required("quantity"),
                registry=self.registry,
                path=f"{owner} measure {measure.code!r} quantity",
            )
            if not isinstance(quantity, pint.Quantity):
                raise SnapshotError(f"{owner} measure quantity is invalid")
            decoded_measures[measure] = quantity

        features: dict[str, object] = {}
        for item in fields.mappings("features"):
            item_fields = Fields(item, owner)
            name = item_fields.text("name")
            if name in features:
                raise SnapshotError(f"{owner} contains duplicate feature {name!r}")
            features[name] = encoded_value.decode(
                item_fields.required("value"),
                registry=self.registry,
                path=f"{owner} feature {name!r}",
            )
        return Characteristics(
            occupancy=occupancy,
            measures=decoded_measures,
            features=features,
        )

    @staticmethod
    def _provenance(value: object, *, owner: str) -> Provenance | None:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise SnapshotError(f"{owner} provenance is invalid")
        fields = Fields(value, f"{owner} provenance")
        identifiers = {}
        for pair in fields.sequence("identifiers"):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise SnapshotError(f"{fields.owner} identifier is invalid")
            key, identifier = pair
            if not isinstance(key, str) or not isinstance(identifier, str):
                raise SnapshotError(f"{fields.owner} identifiers must be strings")
            if key in identifiers:
                raise SnapshotError(
                    f"{fields.owner} contains duplicate identifier {key!r}"
                )
            identifiers[key] = identifier
        return Provenance(source=fields.text("source"), identifiers=identifiers)
