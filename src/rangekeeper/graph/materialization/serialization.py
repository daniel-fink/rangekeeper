from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import networkx as nx
import pint

from ...measure import Measure
from ..assembly import Assembly
from ..characteristics import Characteristics
from ..classification import Classification
from ..entity import Entity
from ..model import Model
from ..provenance import Provenance
from ..relationship import Relationship
from ..taxonomy import Taxonomy
from ..view import View
from . import value as encoded_value
from .errors import SnapshotError
from .fields import Fields
from .record import Record, Snapshot


SCHEMA_VERSION = 2
RECORD_TYPES = frozenset(
    {"taxonomy", "classification", "entity", "assembly", "relationship"}
)


def to_snapshot(source: Model | View) -> Snapshot:
    entities, relationships = _graph_closure(source)
    if isinstance(source, Model):
        taxonomies = source.taxonomies.all()
        classifications = tuple(
            classification
            for taxonomy in taxonomies
            for classification in taxonomy.classifications()
        )
    else:
        classifications = _classification_closure(entities, relationships)
        taxonomies = tuple(
            {classification.taxonomy for classification in classifications}
        )
    records = (
        *(
            Record.from_taxonomy(item)
            for item in sorted(taxonomies, key=lambda item: item.code)
        ),
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
        return source.entities.all(), source.relationships.all()
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
            entity = model.entities[entity_id]
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
        relationship = model.relationships[relationship_id]
        pending_entities.extend((relationship.source_id, relationship.target_id))

    return (
        tuple(
            entity for entity in model.entities.all() if entity.entity_id in entity_ids
        ),
        tuple(
            relationship
            for relationship in model.relationships.all()
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
        for term in classification.taxonomy.classifications():
            existing = by_key.get(term.key)
            if existing is not None and existing is not term:
                raise SnapshotError(f"different Classifications share key {term.key!r}")
            by_key[term.key] = term

    for entity in entities:
        add(entity.classification)
        for classifications in entity.labels.values():
            for classification in classifications:
                add(classification)
    for relationship in relationships:
        add(relationship.classification)
        for classifications in relationship.characteristics.labels.values():
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
    taxonomies: dict[str, Taxonomy] = field(default_factory=dict)
    classifications: dict[str, Classification] = field(default_factory=dict)
    measures: dict[str, Measure] = field(default_factory=dict)
    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    assembly_records: dict[str, Record] = field(default_factory=dict)

    def to_model(self, records: Iterable[Record]) -> Model:
        by_type = self._partition(records)
        self._load_taxonomies(by_type["taxonomy"])
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

    def _load_taxonomies(self, records: Iterable[Record]) -> None:
        for record in records:
            fields = Fields(record.values, f"taxonomy {record.identifier!r}")
            try:
                taxonomy = Taxonomy(
                    code=fields.text("code"),
                    name=fields.text("name"),
                    definition=fields.get("definition"),
                )
            except (TypeError, ValueError) as error:
                raise SnapshotError(f"{fields.owner} is invalid: {error}") from error
            if taxonomy.code != record.identifier:
                raise SnapshotError(
                    f"taxonomy identifier {record.identifier!r} does not match its code"
                )
            self.taxonomies[taxonomy.code] = taxonomy

    def _load_classifications(self, records: Iterable[Record]) -> None:
        grouped: dict[str, list[Record]] = {}
        for record in records:
            fields = Fields(record.values, f"classification {record.identifier!r}")
            taxonomy_code = fields.text("taxonomy")
            if taxonomy_code not in self.taxonomies:
                raise SnapshotError(
                    f"{fields.owner} references missing Taxonomy {taxonomy_code!r}"
                )
            grouped.setdefault(taxonomy_code, []).append(record)

        for taxonomy_code, taxonomy_records in grouped.items():
            taxonomy = self.taxonomies[taxonomy_code]
            by_code: dict[str, Record] = {}
            graph = nx.DiGraph()
            for record in taxonomy_records:
                fields = Fields(record.values, f"classification {record.identifier!r}")
                code = fields.text("code")
                if code in by_code:
                    raise SnapshotError(
                        f"Taxonomy {taxonomy_code!r} contains duplicate code {code!r}"
                    )
                by_code[code] = record
                graph.add_node(code)

            for code, record in by_code.items():
                fields = Fields(record.values, f"classification {record.identifier!r}")
                parent_code = fields.get("parent_code")
                if parent_code is None:
                    continue
                if not isinstance(parent_code, str):
                    raise SnapshotError(f"{fields.owner} parent reference is invalid")
                if parent_code not in by_code:
                    raise SnapshotError(
                        f"{fields.owner} references missing parent {parent_code!r}"
                    )
                graph.add_edge(parent_code, code)

            if not nx.is_directed_acyclic_graph(graph):
                raise SnapshotError(
                    f"Taxonomy {taxonomy_code!r} classification hierarchy has a cycle"
                )
            roots = tuple(code for code, degree in graph.in_degree() if degree == 0)
            if len(roots) != 1:
                raise SnapshotError(
                    f"Taxonomy {taxonomy_code!r} must have exactly one root"
                )

            restored_by_code: dict[str, Classification] = {}
            for code in nx.topological_sort(graph):
                record = by_code[code]
                fields = Fields(record.values, f"classification {record.identifier!r}")
                parent_codes = tuple(graph.predecessors(code))
                parent = None if not parent_codes else restored_by_code[parent_codes[0]]
                try:
                    classification = taxonomy.define(
                        code=code,
                        name=fields.text("name"),
                        definition=fields.get("definition"),
                        parent=parent,
                    )
                except (TypeError, ValueError) as error:
                    raise SnapshotError(
                        f"{fields.owner} is invalid: {error}"
                    ) from error
                if Record.classification_id(classification) != record.identifier:
                    raise SnapshotError(
                        f"classification identifier {record.identifier!r} does not "
                        "match its taxonomy and code"
                    )
                restored_by_code[code] = classification
                self.classifications[record.identifier] = classification

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
            for taxonomy in self.taxonomies.values():
                model.taxonomies.add(taxonomy)
            model.entities.add_all(self.entities.values())
            model.relationships.add_all(self.relationships.values())
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
        labels: dict[str, tuple[Classification, ...]] = {}
        for item in fields.mappings("labels"):
            item_fields = Fields(item, owner)
            key = item_fields.text("key")
            if key in labels:
                raise SnapshotError(f"{owner} contains duplicate label key {key!r}")
            values = tuple(
                self._classification(identifier, owner=owner, required=True)
                for identifier in item_fields.texts("classification_ids", unique=True)
            )
            assert all(value is not None for value in values)
            labels[key] = values

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
            labels=labels,
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
