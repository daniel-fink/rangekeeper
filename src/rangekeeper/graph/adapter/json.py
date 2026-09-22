"""Versioned, typed JSON persistence for RK Graphs with canonical references.

Only the explicitly registered RK types and payload types below are supported.
This is a data format: decoding never imports types or executes source content.
"""

from __future__ import annotations

import json as _json
import math
import os
import re
import tempfile
from dataclasses import fields
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo

import pint

from ...measure import AggregationRule, Index, Measure, QuantityKind
from .. import (
    Assembly,
    Characteristics,
    Classification,
    Definitions,
    Entity,
    Feature,
    Graph,
    Label,
    Measurement,
    Relationship,
    Taxonomy,
)
from ..provenance import (
    AssemblyState,
    Claim,
    ClaimKind,
    EntityState,
    Fact,
    Location,
    Method,
    Provenance,
    Reconciliation,
    ReconciliationStatus,
    RelationshipState,
    Source,
)
from .errors import AdapterEncodingError

__all__ = ["dumps", "loads", "read", "write"]
_TYPES = {
    t.__name__: t
    for t in (
        Graph,
        Definitions,
        Taxonomy,
        Classification,
        Measure,
        Entity,
        Assembly,
        Relationship,
        Characteristics,
        Feature,
        Label,
        Measurement,
        Source,
        Location,
        Method,
        Claim,
        Fact,
        Provenance,
        Reconciliation,
        EntityState,
        AssemblyState,
        RelationshipState,
    )
}
_ENUMS = {
    t.__name__: t
    for t in (AggregationRule, QuantityKind, ClaimKind, ReconciliationStatus)
}
_IDENTIFIED = (
    Taxonomy,
    Classification,
    Measure,
    Entity,
    Assembly,
    Relationship,
    Feature,
    Label,
    Measurement,
    Source,
    Claim,
)
_FORMAT = "rk.graph"


def _fields(obj):
    if type(obj) is Definitions:
        return {
            "taxonomies": tuple(obj.taxonomies.values()),
            "measures": tuple(obj.measures.values()),
        }
    if type(obj) is Taxonomy:
        return {
            "id": obj.id,
            "code": obj.code,
            "name": obj.name,
            "definition": obj.definition,
            "classifications": tuple(obj.classifications.values()),
        }
    return {f.name: getattr(obj, f.name) for f in fields(obj) if f.init}


def dumps(graph: Graph) -> str:
    """Encode a Graph without losing payload types, shared Claims or object order.

    Produces a reloadable reference for independent comparison and later
    inspection; a fingerprint or viewer projection cannot preserve the complete
    graph.
    """
    if not isinstance(graph, Graph):
        raise TypeError("dumps requires a Graph")
    records, active = {}, set()

    def encode(value):
        kind = type(value)
        if value is None or kind in (str, bool):
            return value
        if kind is int:
            return {"int": str(value)}
        if kind is float:
            if not math.isfinite(value):
                raise AdapterEncodingError("Non-finite floats are not supported")
            return {"float": value.hex()}
        if kind is UUID:
            return {"uuid": str(value)}
        if (
            isinstance(value, Enum)
            and kind.__name__ in _ENUMS
            and _ENUMS[kind.__name__] is kind
        ):
            return {"enum": [kind.__name__, value.value]}
        if kind in (datetime, time):
            if value.tzinfo is not None and type(value.tzinfo) not in (
                timezone,
                ZoneInfo,
            ):
                raise AdapterEncodingError("Unsupported timezone type")
            return {
                kind.__name__: [
                    value.isoformat(),
                    value.fold,
                    value.tzinfo.key if isinstance(value.tzinfo, ZoneInfo) else None,
                ]
            }
        if kind is date:
            return {"date": value.isoformat()}
        if kind is timedelta:
            return {"timedelta": [value.days, value.seconds, value.microseconds]}
        if isinstance(value, pint.Quantity):
            return {"quantity": [encode(value.magnitude), str(value.units)]}
        if isinstance(value, pint.Unit):
            return {"unit": str(value)}
        if kind.__name__ in _TYPES and _TYPES[kind.__name__] is kind:
            if isinstance(value, _IDENTIFIED):
                key = f"{kind.__name__}:{value.id}"
                if key in records:
                    original, record = records[key]
                    if original is not value and record is not None:
                        other = {k: encode(v) for k, v in _fields(value).items()}
                        if other != record["fields"]:
                            raise AdapterEncodingError(f"Conflicting identity {key}")
                    return {"ref": key}
                records[key] = (value, None)
                payload = {k: encode(v) for k, v in _fields(value).items()}
                records[key] = (
                    value,
                    {"key": key, "type": kind.__name__, "fields": payload},
                )
                return {"ref": key}
            return {
                "object": kind.__name__,
                "fields": {k: encode(v) for k, v in _fields(value).items()},
            }
        if kind in (dict, MappingProxyType, list, tuple, frozenset):
            if id(value) in active:
                raise AdapterEncodingError("Cyclic payload container")
            active.add(id(value))
            try:
                if kind in (dict, MappingProxyType):
                    return {
                        "mappingproxy" if kind is MappingProxyType else "dict": [
                            [encode(k), encode(v)] for k, v in value.items()
                        ]
                    }
                encoded = [encode(v) for v in value]
                if kind is frozenset:
                    encoded.sort(key=lambda x: _json.dumps(x, sort_keys=True))
                return {kind.__name__: encoded}
            finally:
                active.remove(id(value))
        raise AdapterEncodingError(
            f"Unsupported graph payload type: {kind.__module__}.{kind.__qualname__}"
        )

    root = encode(graph)
    return (
        _json.dumps(
            {
                "format": _FORMAT,
                "version": 1,
                "objects": [records[k][1] for k in sorted(records)],
                "root": root,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdapterEncodingError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def loads(content: str) -> Graph:
    """Decode through normal RK constructors, restoring canonical instances.

    Restores shared evidence and canonical graph targets so loaded Facts satisfy
    the same identity contracts as newly constructed graphs.
    """
    if type(content) is not str:
        raise TypeError("loads requires text")
    try:
        document = _json.loads(content, object_pairs_hook=_unique)
        if (
            set(document) != {"format", "version", "objects", "root"}
            or document["format"] != _FORMAT
            or type(document["version"]) is not int
            or document["version"] != 1
        ):
            raise AdapterEncodingError("Unsupported graph document or version")
        records, built, active = {}, {}, set()
        if type(document["objects"]) is not list:
            raise AdapterEncodingError("objects must be an ordered record list")
        for item in document["objects"]:
            if set(item) != {"key", "type", "fields"} or item["key"] in records:
                raise AdapterEncodingError("Malformed or duplicate identity record")
            if _TYPES.get(item["type"]) not in _IDENTIFIED:
                raise AdapterEncodingError(
                    "Identity record must name an identified RK type"
                )
            records[item["key"]] = item

        def construct(name, payload):
            cls = _TYPES.get(name)
            if cls is None:
                raise AdapterEncodingError(f"Unsupported RK type: {name}")
            expected = (
                {"taxonomies", "measures"}
                if cls is Definitions
                else (
                    {"id", "code", "name", "definition", "classifications"}
                    if cls is Taxonomy
                    else {f.name for f in fields(cls) if f.init}
                )
            )
            if type(payload) is not dict or set(payload) != expected:
                raise AdapterEncodingError(f"Invalid fields for {name}")
            return cls(**{k: decode(v) for k, v in payload.items()})

        def decode(value):
            if value is None or type(value) in (str, bool):
                return value
            if type(value) is not dict:
                raise AdapterEncodingError("Expected a tagged value")
            if set(value) == {"object", "fields"}:
                if _TYPES.get(value["object"]) in _IDENTIFIED:
                    raise AdapterEncodingError("Identified objects require references")
                return construct(value["object"], value["fields"])
            if len(value) != 1:
                raise AdapterEncodingError("Invalid typed value")
            tag, data = next(iter(value.items()))
            if type(tag) is not str:
                raise AdapterEncodingError("Value tags must be text")
            if tag == "ref":
                if data not in records:
                    raise AdapterEncodingError(f"Dangling reference: {data}")
                if data in active:
                    raise AdapterEncodingError(f"Cyclic object reference: {data}")
                if data not in built:
                    active.add(data)
                    record = records[data]
                    item = construct(record["type"], record["fields"])
                    if data != f"{type(item).__name__}:{item.id}":
                        raise AdapterEncodingError(
                            "Identity record key disagrees with UUID"
                        )
                    built[data] = item
                    active.remove(data)
                return built[data]
            if tag == "int" and type(data) is str:
                if re.fullmatch(r"0|-?[1-9][0-9]*", data) is None:
                    raise AdapterEncodingError("Expected canonical integer text")
                return int(data)
            if tag == "float" and type(data) is str:
                result = float.fromhex(data)
                if not math.isfinite(result) or result.hex() != data:
                    raise AdapterEncodingError(
                        "Expected finite canonical hexadecimal float"
                    )
                return result
            if tag == "uuid" and type(data) is str:
                return UUID(data)
            if tag == "enum" and type(data) is list and len(data) == 2:
                name, enum_value = data
                if type(name) is not str or type(enum_value) is not str:
                    raise AdapterEncodingError("Invalid enum payload")
                return _ENUMS[name](enum_value)
            if tag in ("datetime", "time") and type(data) is list and len(data) == 3:
                text, fold, zone = data
                if (
                    type(text) is not str
                    or type(fold) is not int
                    or fold not in (0, 1)
                    or (zone is not None and type(zone) is not str)
                ):
                    raise AdapterEncodingError("Invalid temporal payload")
                result = (datetime if tag == "datetime" else time).fromisoformat(text)
                if zone is not None:
                    # Preserve named-zone semantics as well as its recorded offset.
                    result = result.replace(tzinfo=ZoneInfo(zone), fold=fold)
                    if result.isoformat() != text:
                        raise AdapterEncodingError(
                            "Timezone offset does not match recorded value"
                        )
                return result.replace(fold=fold)
            if tag == "date" and type(data) is str:
                return date.fromisoformat(data)
            if tag == "timedelta" and type(data) is list and len(data) == 3:
                if any(type(v) is not int for v in data):
                    raise AdapterEncodingError("Invalid timedelta payload")
                days, seconds, microseconds = cast(list[int], data)
                if not 0 <= seconds < 86400 or not 0 <= microseconds < 1000000:
                    raise AdapterEncodingError("Invalid timedelta payload")
                return timedelta(days=days, seconds=seconds, microseconds=microseconds)
            if tag == "unit" and type(data) is str:
                return Index.registry.Unit(data)
            if (
                tag == "quantity"
                and type(data) is list
                and len(data) == 2
                and type(data[1]) is str
            ):
                magnitude = decode(data[0])
                if type(magnitude) not in (int, float):
                    raise AdapterEncodingError(
                        "Quantity magnitude must be a supported finite scalar"
                    )
                return Index.registry.Quantity(magnitude, data[1])
            if tag in ("list", "tuple", "frozenset") and type(data) is list:
                items = [decode(v) for v in data]
                if tag == "frozenset" and len(frozenset(items)) != len(items):
                    raise AdapterEncodingError("Duplicate frozenset members")
                return {"list": list, "tuple": tuple, "frozenset": frozenset}[tag](
                    items
                )
            if tag in ("dict", "mappingproxy") and type(data) is list:
                if any(type(pair) is not list or len(pair) != 2 for pair in data):
                    raise AdapterEncodingError(
                        "Mapping entries must be ordered key/value pairs"
                    )
                pairs = [
                    (decode(pair[0]), decode(pair[1]))
                    for pair in cast(list[list[object]], data)
                ]
                result = _unique(pairs)
                return MappingProxyType(result) if tag == "mappingproxy" else result
            raise AdapterEncodingError(f"Unsupported value tag: {tag}")

        graph = decode(document["root"])
        if not isinstance(graph, Graph):
            raise AdapterEncodingError("Root must be a Graph")
        if set(built) != set(records):
            raise AdapterEncodingError("Unreferenced object records")
        return graph
    except AdapterEncodingError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ) as exc:
        raise AdapterEncodingError(f"Invalid graph document: {exc}") from exc


def write(graph: Graph, path: Path) -> Path:
    """Validate/encode first, then atomically replace the requested file.

    Preserves an existing reference if encoding fails, rather than leaving a
    partially written artifact that appears usable.
    """
    content = dumps(graph)
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return path


def read(path: Path) -> Graph:
    """Lets an independent RK process inspect a saved graph without the original
    project runtime or source-to-graph build.
    """
    return loads(Path(path).read_text(encoding="utf-8"))
