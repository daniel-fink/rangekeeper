"""Explicit conversion of the historical RK/Speckle payload used by walkthroughs.

No legacy RK class or Speckle SDK is imported. Collection nesting is transport
structure only. Only relationships declared on an Assembly establish membership.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
import hashlib
import json
from types import MappingProxyType
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from rangekeeper.model import Model
from rangekeeper.model.content import encode
from rangekeeper.schema.runtime import _json_copy
from rangekeeper.schema.validation import document_version
from rangekeeper.adapters.speckle.errors import MappingError

_NAMESPACE = uuid5(NAMESPACE_URL, "urn:rangekeeper:migration:speckle/v1")
_TRANSPORT = {
    "id",
    "speckle_type",
    "totalChildrenCount",
    "applicationId",
    "@displayValue",
    "displayValue",
    "renderMaterial",
}
_DOMAIN = {"entityId", "name", "type", "relationships"}


@dataclass(frozen=True, slots=True)
class MappingSpec:
    """Reviewed field interpretation; no unit or domain kind is inferred.

    Measurement fields map to explicit units. Property fields preserve supported
    JSON content, including null/false/zero. Unlisted fields cause conversion to
    fail. Source name identifies the received artifact, not an authentication key.
    """

    classifications: tuple[str, ...]
    relationships: tuple[str, ...]
    measurements: Mapping[str, str]
    properties: tuple[str, ...] = ()
    source_name: str = "Historical RK Speckle payload"

    def __post_init__(self):
        object.__setattr__(
            self, "measurements", MappingProxyType(dict(self.measurements))
        )
        for field in ("classifications", "relationships", "properties"):
            values = tuple(getattr(self, field))
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate {field}")
            object.__setattr__(self, field, values)
        if set(self.properties) & set(self.measurements):
            raise ValueError("a field cannot be both quantity and property")


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """One complete converted Model, or issues with no partial Model.

    Associations describe transport objects external to the Model. The input
    mapping is never mutated; original geometry remains in the received artifact.
    """

    model: Model | None
    source_sha256: str
    identity_map: tuple[tuple[str, str], ...]
    associations: tuple[Mapping[str, object], ...]
    issues: tuple[str, ...]


def convert_speckle(
    payload: Mapping[str, object],
    *,
    mapping: MappingSpec,
    revision_id: UUID | None = None,
) -> ConversionResult:
    """Convert declared fields and explicit relationships, preserving domain UUIDs.

    The old format represents an Assembly endpoint with null inside its own
    relationship list. This named conversion resolves that endpoint to the owning
    Assembly. Repeated identical records merge; conflicting shared content fails
    with a source path and identity. Geometry and transport IDs never create domain
    membership. Missing quantities remain unresolved, never zero.
    """
    if not isinstance(mapping, MappingSpec):
        raise TypeError("mapping must be MappingSpec")
    data = _json_copy(payload)
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    entities: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    paths: dict[str, list[str]] = {}
    assembly_members: dict[str, set[str]] = {}
    associations: list[dict[str, Any]] = []
    field_paths: dict[tuple[str, str], list[str]] = {}

    def fail(message, path, uid=None):
        raise MappingError(message, path=path, identity=uid)

    def identity(raw, path):
        try:
            return str(UUID(raw))
        except (TypeError, ValueError, AttributeError) as error:
            raise MappingError(
                "expected canonical domain UUID", path=path, identity=str(raw)
            ) from error

    def declaration(kind, key):
        return str(uuid5(_NAMESPACE, f"{kind}:{key}"))

    def endpoint(value, owner, path):
        if value is None:
            return owner
        if isinstance(value, Mapping) and "entityId" in value:
            return identity(value["entityId"], path + "/entityId")
        if isinstance(value, str):
            return identity(value, path)
        fail("unsupported relationship endpoint", path, owner)

    def visit(value, path):
        if isinstance(value, list):
            for i, item in enumerate(value):
                visit(item, f"{path}/{i}")
        elif isinstance(value, dict):
            if "entityId" in value:
                uid = identity(value["entityId"], path + "/entityId")
                is_assembly = "Assembly" in value.get("speckle_type", "")
                unknown = set(value) - (
                    _TRANSPORT
                    | _DOMAIN
                    | set(mapping.properties)
                    | set(mapping.measurements)
                )
                if unknown:
                    fail(f"unsupported source fields: {sorted(unknown)}", path, uid)
                if value.get("type") not in mapping.classifications:
                    fail("unmapped Entity classification", path + "/type", uid)
                content = {
                    k: v
                    for k, v in value.items()
                    if k not in _TRANSPORT | {"relationships"}
                }
                if uid in entities:
                    previous = entities[uid]
                    for key in previous.keys() & content.keys():
                        if (
                            type(previous[key]) is not type(content[key])
                            or previous[key] != content[key]
                        ):
                            # JSON int and float are equal numerical observations;
                            # booleans are never accepted as numerical duplicates.
                            if not (
                                type(previous[key]) in (int, float)
                                and type(content[key]) in (int, float)
                                and previous[key] == content[key]
                            ):
                                fail(
                                    f"conflicting repeated field {key}",
                                    path + "/" + key,
                                    uid,
                                )
                    previous.update(content)
                else:
                    entities[uid] = content
                paths.setdefault(uid, []).append(path)
                for key in content:
                    field_paths.setdefault((uid, key), []).append(path + "/" + key)
                if value.get("id"):
                    item = {"domain_id": uid, "content_id": value["id"]}
                    if value.get("applicationId"):
                        item["application_id"] = value["applicationId"]
                    if item not in associations:
                        associations.append(item)
                relationships = value.get("relationships", [])
                if not isinstance(relationships, list):
                    fail("relationships must be an array", path, uid)
                if relationships and not is_assembly:
                    fail("Entity cannot own relationships", path, uid)
                local = set()
                for i, edge in enumerate(relationships):
                    epath = f"{path}/relationships/{i}"
                    if not isinstance(edge, dict) or set(edge) - (
                        _TRANSPORT | {"source", "target", "type"}
                    ):
                        fail("unsupported relationship fields", epath, uid)
                    left = endpoint(edge.get("source"), uid, epath + "/source")
                    right = endpoint(edge.get("target"), uid, epath + "/target")
                    code = edge.get("type")
                    if code not in mapping.relationships:
                        fail(
                            "unmapped Relationship classification", epath + "/type", uid
                        )
                    key = (left, right, code)
                    eid = declaration("relationship", json.dumps(key))
                    edges[eid] = {
                        "id": eid,
                        "source": left,
                        "target": right,
                        "classification": declaration("classification", code),
                    }
                    paths.setdefault(eid, []).append(epath)
                    local.add(eid)
                if is_assembly:
                    if uid in assembly_members and assembly_members[uid] != local:
                        fail("conflicting Assembly relationship set", path, uid)
                    assembly_members[uid] = local
            # External geometry is retained by the original transport, not interpreted.
            for key, child in value.items():
                if key not in {"@displayValue", "displayValue", "renderMaterial"}:
                    visit(child, path + "/" + key.replace("~", "~0").replace("/", "~1"))

    try:
        visit(data, "")
        if not entities:
            fail("no legacy RK domain records", "/")
        for edge in edges.values():
            if edge["source"] not in entities or edge["target"] not in entities:
                fail("missing relationship endpoint", "/", edge["id"])
        source_id = declaration("source", digest)
        claims = []
        facts = []

        def evidence(target, content, source_paths):
            cid = declaration("claim", digest + ":" + target)
            claims.append(
                {
                    "id": cid,
                    "kind": "sourced",
                    "content": content,
                    "sources": [
                        {"source": source_id, "address": {"path": p}}
                        for p in dict.fromkeys(source_paths)
                    ],
                }
            )
            facts.append({"target": target, "claims": [cid]})

        objects = []
        groups = []
        for uid, raw in sorted(entities.items()):
            values = []
            for key in (*mapping.measurements, *mapping.properties):
                if key not in raw:
                    continue
                vid = str(uuid5(UUID(uid), "value:" + key))
                value: dict[str, Any] = {"id": vid, "key": key}
                if key in mapping.measurements:
                    magnitude = raw[key]
                    if magnitude is not None and type(magnitude) not in (float, int):
                        fail(
                            "quantity must be numeric or null",
                            paths[uid][0] + "/" + key,
                            uid,
                        )
                    value.update(
                        kind="measurement",
                        measure=declaration("measure", key),
                        quantity=(
                            None
                            if magnitude is None
                            else {
                                "magnitude": magnitude,
                                "units": mapping.measurements[key],
                            }
                        ),
                    )
                else:
                    value.update(kind="property", content=encode(raw[key]).to_data())
                values.append(value)
                evidence(
                    vid,
                    {"source_field": key, "value": raw[key]},
                    field_paths[(uid, key)],
                )
            obj = {
                "id": uid,
                "name": raw.get("name"),
                "classification": declaration("classification", raw["type"]),
                "characteristics": {"values": values},
            }
            if uid in assembly_members:
                links = sorted(assembly_members[uid])
                members = {
                    edges[e][side] for e in links for side in ("source", "target")
                } - {uid}
                obj.update(entities=sorted(members), relationships=links)
                groups.append(obj)
            else:
                objects.append(obj)
            evidence(uid, raw, paths[uid])
        for uid, edge in sorted(edges.items()):
            evidence(uid, edge, paths[uid])
        root = declaration("classification", "rk-design-object")
        classes = [
            {"id": root, "code": "rk-design-object", "name": "RK design object"}
        ] + [
            {
                "id": declaration("classification", code),
                "code": code,
                "name": code,
                "parent": root,
            }
            for code in dict.fromkeys(
                (*mapping.classifications, *mapping.relationships)
            )
        ]
        model = Model.from_data(
            {
                "metadata": {
                    "id": str(revision_id or uuid4()),
                    "schema_version": document_version("Model"),
                },
                "definitions": {
                    "taxonomies": [
                        {
                            "id": declaration("taxonomy", "design"),
                            "code": "design",
                            "name": "Design",
                            "classifications": classes,
                        }
                    ],
                    "measures": [
                        {
                            "id": declaration("measure", key),
                            "code": key,
                            "name": key,
                            "units": unit,
                        }
                        for key, unit in mapping.measurements.items()
                    ],
                },
                "system": {
                    "entities": objects,
                    "assemblies": groups,
                    "relationships": [edges[k] for k in sorted(edges)],
                },
                "provenance": {
                    "sources": [
                        {
                            "id": source_id,
                            "name": mapping.source_name,
                            "checksum": digest,
                        }
                    ],
                    "claims": claims,
                    "facts": facts,
                },
            }
        )
        frozen_associations = tuple(
            MappingProxyType({"model_revision": str(model.id), **a})
            for a in associations
        )
        return ConversionResult(
            model,
            digest,
            tuple((uid, uid) for uid in sorted(entities)),
            frozen_associations,
            (),
        )
    except (ValueError, TypeError, LookupError) as error:
        return ConversionResult(None, digest, (), (), (str(error),))
