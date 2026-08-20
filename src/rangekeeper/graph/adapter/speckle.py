from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from specklepy.objects import Base

from ..assembly import Assembly
from ..characteristics import Characteristics
from ..entity import Entity
from ..materialization import Record, Snapshot, UnsupportedValueError, to_snapshot
from ..materialization import value as encoded_value
from ..model import Model
from ..provenance import Provenance
from ..relationship import Relationship
from ..taxonomy import Taxonomy
from ..view import View
from .errors import AdapterEncodingError, SpeckleConflictError, SpeckleImportError


PACKAGE_KIND = "rangekeeper.snapshot"
PACKAGE_SCHEMA_VERSION = 1
ENTITY_TAXONOMY_CODE = "legacy.entity_type"
RELATIONSHIP_TAXONOMY_CODE = "legacy.relationship_type"
LABEL_TAXONOMY_PREFIX = "legacy.labels."

_TECHNICAL_MEMBERS = frozenset(
    {
        "@displayValue",
        "applicationId",
        "displayValue",
        "entityId",
        "graph",
        "id",
        "name",
        "relationships",
        "renderMaterial",
        "speckle_type",
        "totalChildrenCount",
        "type",
        "units",
    }
)
_LABEL_MEMBERS = frozenset({"use", "tenure"})


class SnapshotPackage(Base):
    pass


class SnapshotRecord(Base):
    pass


def load(
    base: Base,
    *,
    context: Mapping[str, str] | None = None,
) -> Model:
    """Load a legacy design or explicit Rangekeeper Snapshot package."""
    if not isinstance(base, Base):
        raise TypeError("base must be a Speckle Base")
    normalized_context = _validated_context(context)
    if _member(base, "packageKind") == PACKAGE_KIND:
        return _load_package(base)
    return _LegacyImporter(normalized_context).load(base)


def dump(source: Model | View) -> Base:
    """Dump a Model or View as an explicit, Snapshot-backed Speckle package."""
    if not isinstance(source, (Model, View)):
        raise TypeError("source must be a Model or View")
    snapshot = to_snapshot(source)
    package = SnapshotPackage()
    package["packageKind"] = PACKAGE_KIND
    package["packageSchemaVersion"] = PACKAGE_SCHEMA_VERSION
    package["snapshotSchemaVersion"] = snapshot.schema_version
    package["records"] = []
    for record in snapshot.records:
        item = SnapshotRecord()
        item["recordType"] = record.record_type
        item["identifier"] = record.identifier
        item["values"] = _plain_value(record.values)
        package["records"].append(item)
    return package


def _load_package(base: Base) -> Model:
    package_version = _member(base, "packageSchemaVersion")
    if package_version != PACKAGE_SCHEMA_VERSION:
        raise AdapterEncodingError(
            f"unsupported Speckle package schema version {package_version!r}"
        )
    snapshot_version = _member(base, "snapshotSchemaVersion")
    if type(snapshot_version) is not int:
        raise AdapterEncodingError("Speckle package snapshotSchemaVersion is invalid")
    raw_records = _member(base, "records")
    if not isinstance(raw_records, (list, tuple)):
        raise AdapterEncodingError("Speckle package records must be a list")
    records = []
    for index, item in enumerate(raw_records):
        if not isinstance(item, Base):
            raise AdapterEncodingError(f"Speckle package record {index} must be a Base")
        try:
            records.append(
                Record(
                    record_type=_required_text(item, "recordType"),
                    identifier=_required_text(item, "identifier"),
                    values=_plain_speckle_value(_member(item, "values")),
                )
            )
        except (TypeError, ValueError) as error:
            raise AdapterEncodingError(
                f"Speckle package record {index} is invalid: {error}"
            ) from error
    try:
        snapshot = Snapshot(schema_version=snapshot_version, records=tuple(records))
        return Model.from_snapshot(snapshot)
    except (TypeError, ValueError) as error:
        raise AdapterEncodingError(f"Speckle package is invalid: {error}") from error


@dataclass
class _LegacyRepresentation:
    entity_id: str
    name: str | None
    type_code: str
    is_assembly: bool
    features: dict[str, object]
    labels: dict[str, tuple[str, ...]]
    provenance: Provenance
    relationship_bases: tuple[Base, ...]


@dataclass
class _LegacyImporter:
    context: dict[str, str]
    representations: dict[str, _LegacyRepresentation] = field(default_factory=dict)
    _seen_bases: set[int] = field(default_factory=set)

    def load(self, root: Base) -> Model:
        self._walk(root)
        if not self.representations:
            raise SpeckleImportError("Speckle object graph contains no entityId values")

        entity_taxonomy, entity_types = _legacy_taxonomy(
            ENTITY_TAXONOMY_CODE,
            "Legacy Entity Types",
            "entity",
            (item.type_code for item in self.representations.values()),
        )
        relationship_type_codes = tuple(
            self._relationship_type(base)
            for item in self.representations.values()
            for base in item.relationship_bases
        )
        relationship_taxonomy, relationship_types = _legacy_taxonomy(
            RELATIONSHIP_TAXONOMY_CODE,
            "Legacy Relationship Types",
            "relationship",
            relationship_type_codes,
        )
        label_taxonomies = self._label_taxonomies()

        entities: dict[str, Entity] = {}
        for item in self.representations.values():
            labels = {
                key: tuple(label_taxonomies[key][1][code] for code in codes)
                for key, codes in item.labels.items()
            }
            entity_class = Assembly if item.is_assembly else Entity
            entities[item.entity_id] = entity_class(
                entity_id=item.entity_id,
                name=item.name,
                classification=entity_types[item.type_code],
                characteristics=Characteristics(
                    labels=labels,
                    features=item.features,
                ),
                provenance=item.provenance,
            )

        relationships: dict[str, Relationship] = {}
        assembly_relationship_ids: dict[str, list[str]] = {}
        edge_counts: dict[tuple[str, str, str], int] = {}
        for item in self.representations.values():
            if not item.is_assembly:
                continue
            for base in item.relationship_bases:
                source_id = self._endpoint_id(base, "source", item.entity_id)
                target_id = self._endpoint_id(base, "target", item.entity_id)
                for endpoint_id in (source_id, target_id):
                    if endpoint_id not in entities:
                        raise SpeckleImportError(
                            f"relationship in Assembly {item.entity_id!r} references "
                            f"missing Entity {endpoint_id!r}"
                        )
                type_code = self._relationship_type(base)
                edge_key = (source_id, target_id, type_code)
                occurrence = edge_counts.get(edge_key, 0)
                edge_counts[edge_key] = occurrence + 1
                relationship_id = _relationship_id(base, edge_key, occurrence)
                if relationship_id in relationships:
                    existing = relationships[relationship_id]
                    if (
                        existing.source_id,
                        existing.target_id,
                        existing.classification.code,
                    ) != edge_key:
                        raise SpeckleConflictError(
                            f"Speckle relationships conflict on ID {relationship_id!r}"
                        )
                else:
                    relationships[relationship_id] = Relationship(
                        source_id,
                        target_id,
                        relationship_types[type_code],
                        relationship_id=relationship_id,
                        provenance=_provenance(base, self.context),
                    )
                assembly_relationship_ids.setdefault(item.entity_id, []).append(
                    relationship_id
                )

        for assembly_id, relationship_ids in assembly_relationship_ids.items():
            assembly = entities[assembly_id]
            assert isinstance(assembly, Assembly)
            assembly_relationships = tuple(
                relationships[relationship_id] for relationship_id in relationship_ids
            )
            member_ids = {
                endpoint_id
                for relationship in assembly_relationships
                for endpoint_id in (relationship.source_id, relationship.target_id)
                if endpoint_id != assembly_id
            }
            assembly._replace_contents(
                entities=tuple(entities[entity_id] for entity_id in member_ids),
                relationships=assembly_relationships,
            )

        model = Model()
        for taxonomy in (
            entity_taxonomy,
            relationship_taxonomy,
            *(taxonomy for taxonomy, _ in label_taxonomies.values()),
        ):
            model.taxonomies.add(taxonomy)
        model.entities.add_all(entities.values())
        model.relationships.add_all(relationships.values())
        validation = model.validate()
        if not validation:
            messages = "; ".join(issue.message for issue in validation.issues)
            raise SpeckleImportError(f"imported Speckle graph is invalid: {messages}")
        return model

    def _walk(self, value: object) -> None:
        if isinstance(value, Base):
            identity = id(value)
            if identity in self._seen_bases:
                return
            self._seen_bases.add(identity)
            entity_id = _optional_text(value, "entityId")
            if entity_id is not None:
                candidate = self._representation(value, entity_id)
                existing = self.representations.get(entity_id)
                self.representations[entity_id] = (
                    candidate
                    if existing is None
                    else _merge_representations(existing, candidate)
                )
            for member_name in value.get_member_names():
                if member_name in {"id", "applicationId", "speckle_type"}:
                    continue
                self._walk(_member(value, member_name))
            return
        if isinstance(value, Mapping):
            for item in value.values():
                self._walk(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                self._walk(item)

    def _representation(self, base: Base, entity_id: str) -> _LegacyRepresentation:
        labels = {}
        features = {}
        for member_name in base.get_dynamic_member_names():
            if member_name in _TECHNICAL_MEMBERS:
                continue
            value = _member(base, member_name)
            if member_name in _LABEL_MEMBERS:
                codes = _label_codes(value)
                if codes is not None:
                    labels[member_name] = codes
                    continue
            if _contains_entity(value):
                continue
            feature = _legacy_feature_value(
                value,
                path=f"Speckle Entity {entity_id!r} feature {member_name!r}",
            )
            try:
                encoded_value.encode(
                    feature,
                    path=f"Speckle Entity {entity_id!r} feature {member_name!r}",
                )
            except UnsupportedValueError as error:
                raise SpeckleImportError(str(error)) from error
            features[member_name] = feature
        relationship_bases = _relationship_bases(base)
        return _LegacyRepresentation(
            entity_id=entity_id,
            name=_optional_text(base, "name"),
            type_code=_optional_text(base, "type") or "unknown",
            is_assembly=("Assembly" in base.speckle_type or bool(relationship_bases)),
            features=features,
            labels=labels,
            provenance=_provenance(base, self.context),
            relationship_bases=relationship_bases,
        )

    def _label_taxonomies(
        self,
    ) -> dict[str, tuple[Taxonomy, dict[str, object]]]:
        result = {}
        keys = sorted(
            {key for item in self.representations.values() for key in item.labels}
        )
        for key in keys:
            result[key] = _legacy_taxonomy(
                f"{LABEL_TAXONOMY_PREFIX}{key}",
                f"Legacy {key.title()} Labels",
                "label",
                (
                    code
                    for item in self.representations.values()
                    for code in item.labels.get(key, ())
                ),
            )
        return result

    @staticmethod
    def _relationship_type(base: Base) -> str:
        return _optional_text(base, "type") or "unknown"

    @staticmethod
    def _endpoint_id(base: Base, member_name: str, assembly_id: str) -> str:
        endpoint = _member(base, member_name)
        if endpoint is None:
            return assembly_id
        if isinstance(endpoint, Base):
            return _required_text(endpoint, "entityId")
        if isinstance(endpoint, Mapping):
            value = endpoint.get("entityId")
            if isinstance(value, str) and value.strip():
                return value
        raise SpeckleImportError(
            f"relationship {member_name} must be None or reference an entityId"
        )


def _legacy_taxonomy(
    code: str,
    name: str,
    root_code: str,
    values: object,
) -> tuple[Taxonomy, dict[str, object]]:
    taxonomy = Taxonomy(code=code, name=name)
    root = taxonomy.define(code=root_code, name=root_code.title())
    classifications = {root_code: root}
    for value in sorted(set(values)):
        if value == root_code:
            continue
        classifications[value] = root.define(code=value, name=value)
    return taxonomy, classifications


def _merge_representations(
    existing: _LegacyRepresentation,
    candidate: _LegacyRepresentation,
) -> _LegacyRepresentation:
    name = _merged_scalar(existing.name, candidate.name, existing.entity_id, "name")
    type_code = _merged_scalar(
        existing.type_code,
        candidate.type_code,
        existing.entity_id,
        "type",
    )
    features = dict(existing.features)
    for key, value in candidate.features.items():
        if key in features and _encoded(features[key]) != _encoded(value):
            raise SpeckleConflictError(
                f"duplicate Speckle Entity {existing.entity_id!r} has conflicting "
                f"feature {key!r}"
            )
        features[key] = value
    labels = dict(existing.labels)
    for key, values in candidate.labels.items():
        labels[key] = tuple(dict.fromkeys((*labels.get(key, ()), *values)))
    relationship_bases = tuple(
        dict.fromkeys((*existing.relationship_bases, *candidate.relationship_bases))
    )
    provenance = Provenance(
        source="speckle",
        identifiers={
            **existing.provenance.identifiers,
            **candidate.provenance.identifiers,
        },
    )
    return _LegacyRepresentation(
        entity_id=existing.entity_id,
        name=name,
        type_code=type_code,
        is_assembly=existing.is_assembly or candidate.is_assembly,
        features=features,
        labels=labels,
        provenance=provenance,
        relationship_bases=relationship_bases,
    )


def _merged_scalar(
    existing: str | None,
    candidate: str | None,
    entity_id: str,
    field_name: str,
) -> str | None:
    if existing is None:
        return candidate
    if candidate is None or existing == candidate:
        return existing
    raise SpeckleConflictError(
        f"duplicate Speckle Entity {entity_id!r} has conflicting {field_name} values"
    )


def _encoded(value: object) -> object:
    return encoded_value.encode(value, path="duplicate Speckle value")


def _relationship_bases(base: Base) -> tuple[Base, ...]:
    relationships = _member(base, "relationships")
    if relationships is None:
        return ()
    if not isinstance(relationships, (list, tuple)):
        raise SpeckleImportError("Assembly relationships must be a list")
    if not all(isinstance(item, Base) for item in relationships):
        raise SpeckleImportError("Assembly relationships must contain only Bases")
    return tuple(relationships)


def _relationship_id(
    base: Base,
    edge_key: tuple[str, str, str],
    occurrence: int,
) -> str:
    supplied = _optional_text(base, "applicationId") or _optional_text(base, "id")
    if supplied is not None:
        return supplied
    source_id, target_id, type_code = edge_key
    return f"legacy:{type_code}:{source_id}:{target_id}:{occurrence}"


def _provenance(base: Base, context: Mapping[str, str]) -> Provenance:
    identifiers = dict(context)
    for source_name, target_name in (
        ("id", "object_id"),
        ("applicationId", "application_id"),
    ):
        value = _optional_text(base, source_name)
        if value is not None:
            identifiers[target_name] = value
    if not identifiers:
        identifiers["entity_id"] = _optional_text(base, "entityId") or "unknown"
    return Provenance(source="speckle", identifiers=identifiers)


def _validated_context(context: Mapping[str, str] | None) -> dict[str, str]:
    if context is None:
        return {}
    if not isinstance(context, Mapping):
        raise TypeError("context must be a mapping or None")
    result = dict(context)
    if not all(
        isinstance(key, str)
        and key.strip()
        and isinstance(value, str)
        and value.strip()
        for key, value in result.items()
    ):
        raise ValueError("context keys and values must be non-empty strings")
    return result


def _label_codes(value: object) -> tuple[str, ...] | None:
    if isinstance(value, str) and value.strip():
        return (value,)
    if isinstance(value, (list, tuple)) and all(
        isinstance(item, str) and item.strip() for item in value
    ):
        return tuple(dict.fromkeys(value))
    return None


def _contains_entity(value: object) -> bool:
    if isinstance(value, Base):
        return _optional_text(value, "entityId") is not None
    if isinstance(value, Mapping):
        return any(_contains_entity(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_entity(item) for item in value)
    return False


def _legacy_feature_value(value: object, *, path: str) -> object:
    if isinstance(value, Base):
        result = {}
        for name in value.get_dynamic_member_names():
            if name in _TECHNICAL_MEMBERS:
                continue
            result[name] = _legacy_feature_value(
                _member(value, name), path=f"{path}.{name}"
            )
        return result
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise SpeckleImportError(f"{path} contains a non-string mapping key")
        return {
            key: _legacy_feature_value(item, path=f"{path}.{key}")
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(
            _legacy_feature_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if isinstance(value, list):
        return [
            _legacy_feature_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    return value


def _plain_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    return value


def _plain_speckle_value(value: object) -> object:
    if isinstance(value, Base):
        return {
            name: _plain_speckle_value(_member(value, name))
            for name in value.get_dynamic_member_names()
        }
    if isinstance(value, Mapping):
        return {key: _plain_speckle_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_plain_speckle_value(item) for item in value)
    return value


def _member(base: Base, name: str) -> object:
    try:
        return base[name]
    except (KeyError, AttributeError):
        return None


def _optional_text(base: Base, name: str) -> str | None:
    value = _member(base, name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _required_text(base: Base, name: str) -> str:
    value = _optional_text(base, name)
    if value is None:
        raise SpeckleImportError(f"Speckle member {name!r} must be a non-empty string")
    return value
