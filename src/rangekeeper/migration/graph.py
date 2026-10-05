"""Bounded rk.graph/v1 conversion without importing the retired Graph implementation.

The decoder recognizes inert wire tags and a closed historical field inventory.
A conversion returns either a validated Model or issues, never an incomplete Model.
The original bytes and their hash identify the source; no filesystem writes occur.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import hashlib
import json
import math
from types import MappingProxyType
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from ..model import Model
from ..model.content import encode
from .._schema.validation import document_version
from .._records import _json_copy


@dataclass(frozen=True, slots=True)
class ConversionResult:
    model: Model | None
    source_sha256: str
    identity_map: tuple[tuple[str, str], ...]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class _Node:
    kind: str
    fields: dict


@dataclass(frozen=True)
class _Unit:
    text: str


@dataclass(frozen=True)
class _Quantity:
    magnitude: float
    units: str


# This is an old-format reader contract, not a second schema for the new Model.
_FIELDS = {
    "Graph": "definitions entities relationships provenance",
    "Definitions": "taxonomies measures",
    "Taxonomy": "id code name definition classifications",
    "Classification": "id code name definition parent",
    "Measure": "id code name definition units quantity_kind aggregation tags",
    "Entity": "id code name classification characteristics",
    "Assembly": "id code name classification characteristics entity_ids relationship_ids",
    "Relationship": "id source_id target_id classification characteristics",
    "Characteristics": "labels measurements features",
    "Feature": "id name value",
    "Label": "id key classifications",
    "Measurement": "id measure quantity",
    "Source": "id name checksum issued_at received_at author",
    "Claim": "id value kind sources method",
    "Location": "source reference",
    "Method": "code version description",
    "Provenance": "facts",
    "Fact": "target claims reconciliation",
    "Reconciliation": "selected status method",
    "EntityState": "code name classification",
    "AssemblyState": "code name classification entity_ids relationship_ids",
    "RelationshipState": "source_id target_id classification",
}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def convert_graph(
    text: str,
    *,
    revision_id: UUID | None = None,
    value_keys: dict[str, str] | None = None,
) -> ConversionResult:
    """Convert the supported v1 format; retain UUIDs and require explicit key conflicts.

    Measurements use their old Measure code; Features use their name. ``value_keys``
    maps old Value UUID strings to reviewed replacement keys when names collide.
    Historical Measure quantity-kind and aggregation declarations survive as tags;
    they do not silently select a new reducer. Existing claim payload wire tags are
    retained under an explicit encoding label rather than reinterpreted as equations.
    """
    digest = hashlib.sha256(text.encode()).hexdigest()
    identities = {}
    try:
        document = json.loads(
            text,
            object_pairs_hook=_unique,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"invalid JSON: {token}")
            ),
        )
        if (
            set(document) != {"format", "version", "objects", "root"}
            or document["format"] != "rk.graph"
            or document["version"] != 1
        ):
            raise ValueError("expected rk.graph version 1")
        records = {}
        for record in document["objects"]:
            if set(record) != {"key", "type", "fields"} or record["key"] in records:
                raise ValueError("malformed or duplicate legacy record")
            records[record["key"]] = record
        built, active = {}, set()

        def construct(kind, fields):
            if kind not in _FIELDS or set(fields) != set(_FIELDS[kind].split()):
                raise ValueError(f"unsupported fields or type: {kind}")
            return _Node(kind, {key: decode(value) for key, value in fields.items()})

        def decode(value):
            if value is None or type(value) in (str, bool):
                return value
            if not isinstance(value, dict):
                raise ValueError("expected tagged legacy value")
            if set(value) == {"object", "fields"}:
                return construct(value["object"], value["fields"])
            if len(value) != 1:
                raise ValueError("invalid legacy tag")
            tag, data = next(iter(value.items()))
            if tag == "ref":
                if data not in records or data in active:
                    raise ValueError("missing or cyclic legacy reference")
                if data not in built:
                    active.add(data)
                    record = records[data]
                    node = construct(record["type"], record["fields"])
                    if data != f"{node.kind}:{node.fields['id']}":
                        raise ValueError("legacy identity key mismatch")
                    built[data] = node
                    active.remove(data)
                return built[data]
            if tag == "uuid":
                return UUID(data)
            if tag == "int":
                result = int(data)
                if str(result) != data:
                    raise ValueError("noncanonical integer")
                return result
            if tag == "float":
                result = float.fromhex(data)
                if not math.isfinite(result) or result.hex() != data:
                    raise ValueError("invalid legacy float")
                return result
            if tag == "unit":
                return _Unit(data)
            if tag == "enum":
                if data[0] not in {
                    "AggregationRule",
                    "QuantityKind",
                    "ClaimKind",
                    "ReconciliationStatus",
                }:
                    raise ValueError("unsupported legacy enum")
                return data[1]
            if tag == "quantity":
                return _Quantity(decode(data[0]), data[1])
            if tag == "date":
                return date.fromisoformat(data)
            if tag in ("datetime", "time"):
                stamp, fold, zone = data
                result = (
                    (datetime if tag == "datetime" else time)
                    .fromisoformat(stamp)
                    .replace(fold=fold)
                )
                if zone:
                    result = result.replace(tzinfo=ZoneInfo(zone))
                    if result.isoformat() != stamp:
                        raise ValueError("legacy timezone offset mismatch")
                return result
            if tag == "timedelta":
                return timedelta(days=data[0], seconds=data[1], microseconds=data[2])
            if tag in ("list", "tuple", "frozenset"):
                items = [decode(x) for x in data]
                result = {"list": list, "tuple": tuple, "frozenset": frozenset}[tag](
                    items
                )
                if len(result) != len(items):
                    raise ValueError("duplicate legacy set member")
                return result
            if tag in ("dict", "mappingproxy"):
                result = _unique((decode(k), decode(v)) for k, v in data)
                return MappingProxyType(result) if tag == "mappingproxy" else result
            raise ValueError(f"unsupported legacy tag: {tag}")

        root = decode(document["root"])
        if not isinstance(root, _Node) or root.kind != "Graph":
            raise ValueError("root is not a Graph")
        if set(built) != set(records):
            raise ValueError("unreferenced legacy objects")

        def identity(node):
            value = str(node.fields["id"])
            identities[value] = value
            return value

        def fields(node, names):
            return {
                name: node.fields[name]
                for name in names.split()
                if node.fields[name] is not None
            }

        definitions = root.fields["definitions"].fields
        measures = []
        for node in definitions["measures"]:
            measures.append(
                dict(
                    id=identity(node),
                    **fields(node, "code name definition"),
                    units=node.fields["units"].text,
                    tags=[
                        *node.fields["tags"],
                        f"legacy.quantity_kind:{node.fields['quantity_kind']}",
                        f"legacy.aggregation:{node.fields['aggregation']}",
                    ],
                )
            )
        taxonomies = []
        for node in definitions["taxonomies"]:
            classifications = []
            for c in node.fields["classifications"]:
                record = dict(id=identity(c), **fields(c, "code name definition"))
                if c.fields["parent"] is not None:
                    record["parent"] = identity(c.fields["parent"])
                classifications.append(record)
            taxonomies.append(
                dict(
                    id=identity(node),
                    **fields(node, "code name definition"),
                    classifications=classifications,
                )
            )

        def characteristics(node):
            data = node.fields
            values = []
            labels = []
            for item in data["measurements"].values():
                key = (value_keys or {}).get(
                    str(item.fields["id"]), item.fields["measure"].fields["code"]
                )
                values.append(
                    dict(
                        id=identity(item),
                        key=key,
                        kind="measurement",
                        measure=identity(item.fields["measure"]),
                        quantity=dict(
                            magnitude=item.fields["quantity"].magnitude,
                            units=item.fields["quantity"].units,
                        ),
                    )
                )
            for item in data["features"].values():
                key = (value_keys or {}).get(
                    str(item.fields["id"]), item.fields["name"]
                )
                values.append(
                    dict(
                        id=identity(item),
                        key=key,
                        kind="property",
                        content=encode(item.fields["value"]).to_data(),
                    )
                )
            for item in data["labels"].values():
                labels.append(
                    dict(
                        id=identity(item),
                        key=item.fields["key"],
                        classifications=[
                            identity(c) for c in item.fields["classifications"]
                        ],
                    )
                )
            return dict(values=values, labels=labels)

        entities, assemblies, relationships = [], [], []
        for node in root.fields["entities"]:
            record = dict(
                id=identity(node),
                **fields(node, "code name"),
                characteristics=characteristics(node.fields["characteristics"]),
            )
            if node.fields["classification"] is not None:
                record["classification"] = identity(node.fields["classification"])
            if node.kind == "Assembly":
                record.update(
                    entities=sorted(str(i) for i in node.fields["entity_ids"]),
                    relationships=sorted(
                        str(i) for i in node.fields["relationship_ids"]
                    ),
                )
                assemblies.append(record)
            elif node.kind == "Entity":
                entities.append(record)
            else:
                raise ValueError("unsupported entity kind")
        for node in root.fields["relationships"]:
            relationships.append(
                dict(
                    id=identity(node),
                    source=str(node.fields["source_id"]),
                    target=str(node.fields["target_id"]),
                    classification=identity(node.fields["classification"]),
                    characteristics=characteristics(node.fields["characteristics"]),
                )
            )

        def referenced_records(payload):
            # A claim can refer to a historical Classification/Measure or entity
            # state. Retain the transitive wire objects so its content is self-contained.
            required = {}

            def visit(item):
                if isinstance(item, dict):
                    if set(item) == {"ref"} and item["ref"] not in required:
                        record = records[item["ref"]]
                        required[item["ref"]] = record
                        visit(record["fields"])
                    else:
                        for child in item.values():
                            visit(child)
                elif isinstance(item, list):
                    for child in item:
                        visit(child)

            visit(payload)
            return [required[key] for key in sorted(required)]

        sources, claims = [], []
        for node in built.values():
            if node.kind == "Source":
                record = dict(id=identity(node), **fields(node, "name checksum author"))
                for key in ("issued_at", "received_at"):
                    if node.fields[key] is not None:
                        record[key] = node.fields[key].isoformat()
                sources.append(record)
            if node.kind == "Claim":
                support = []
                for parent in node.fields["sources"]:
                    if parent.kind == "Claim":
                        support.append(identity(parent))
                    elif parent.kind == "Location":
                        support.append(
                            dict(
                                source=identity(parent.fields["source"]),
                                address=dict(parent.fields["reference"]),
                            )
                        )
                    else:
                        raise ValueError("unsupported Claim support")
                payload = records[f"Claim:{node.fields['id']}"]["fields"]["value"]
                record = dict(
                    id=identity(node),
                    kind=node.fields["kind"],
                    content={
                        "encoding": "rk.graph-value/v1",
                        "value": payload,
                        "objects": referenced_records(payload),
                    },
                    sources=support,
                )
                if node.fields["method"] is not None:
                    record["method"] = fields(
                        node.fields["method"], "code version description"
                    )
                claims.append(record)
        facts = []
        for node in root.fields["provenance"].fields["facts"]:
            record = dict(
                target=identity(node.fields["target"]),
                claims=[identity(c) for c in node.fields["claims"]],
            )
            reconciliation = node.fields["reconciliation"]
            if reconciliation is not None:
                r = dict(
                    selected=identity(reconciliation.fields["selected"]),
                    status=reconciliation.fields["status"],
                )
                if reconciliation.fields["method"] is not None:
                    r["method"] = fields(
                        reconciliation.fields["method"], "code version description"
                    )
                record["reconciliation"] = r
            facts.append(record)
        data = dict(
            metadata=dict(
                id=str(revision_id or uuid4()), schema_version=document_version("Model")
            ),
            definitions=dict(measures=measures, taxonomies=taxonomies),
            system=dict(
                entities=entities, assemblies=assemblies, relationships=relationships
            ),
            provenance=dict(sources=sources, claims=claims, facts=facts),
        )
        if value_keys is not None:
            known_values = {
                str(n.fields["id"])
                for n in built.values()
                if n.kind in {"Measurement", "Feature"}
            }
            if not isinstance(value_keys, dict) or set(value_keys) - known_values:
                raise ValueError("value_keys contains unknown Value UUIDs")
        model = Model.from_data(data)
        return ConversionResult(model, digest, tuple(sorted(identities.items())), ())
    except (ValueError, TypeError, LookupError, AttributeError, OverflowError) as error:
        return ConversionResult(
            None, digest, tuple(sorted(identities.items())), (str(error),)
        )


def upgrade_model(data: dict, *, revision_id: UUID | None = None) -> Model:
    """Explicitly upgrade a scalar Model 0.3.0 to a new 0.4.0 revision.

    Declaration UUIDs and source provenance stay intact. The old revision remains
    immutable; previous points to it. Ordinary codecs reject the old version.
    """
    result = _json_copy(data)
    if result.get("metadata", {}).get("schema_version") != "0.3.0":
        raise ValueError("expected Model schema version 0.3.0")
    old = result["metadata"]["id"]
    if revision_id is not None and str(revision_id) == old:
        raise ValueError("upgrade requires a new revision UUID")
    result["metadata"].update(
        id=str(revision_id or uuid4()),
        previous=old,
        schema_version=document_version("Model"),
    )
    return Model.from_data(result)
