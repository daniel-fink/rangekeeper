"""Encode inert property content without losing scalar or container types.

The field schema is generated from LinkML. Exports are detached Python objects;
mutable lists/dicts returned by ``decode`` cannot change the canonical record.
No class name, pickle, import path, or callback is executed during decoding.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
import json
import math
from types import MappingProxyType
from uuid import UUID
from zoneinfo import ZoneInfo

from .._schema.records import PropertyContent


def encode(value: object) -> PropertyContent:
    """Copy a supported Python value to typed, immutable schema content.

    Cycles, non-finite numbers, and unsupported classes raise ValueError/TypeError.
    Mapping insertion order and list/tuple distinctions survive interchange.
    """
    active: set[int] = set()

    def visit(item):
        if item is None:
            return {"kind": "null"}
        typ = type(item)
        if typ in (bool, int, float, str):
            if typ is float and not math.isfinite(item):
                raise ValueError("property numbers must be finite")
            kind = {bool: "boolean", int: "integer", float: "float", str: "string"}[typ]
            return {"kind": kind, "text": item if typ is str else repr(item)}
        if typ is UUID:
            return {"kind": "uuid", "text": str(item)}
        if typ in (date, datetime, time):
            result = {"kind": typ.__name__, "text": item.isoformat()}
            if typ in (datetime, time):
                result["fold"] = item.fold
                zone = getattr(item.tzinfo, "key", None)
                if zone:
                    result["zone"] = zone
            return result
        if typ is timedelta:
            micros = (item.days * 86400 + item.seconds) * 1_000_000 + item.microseconds
            return {"kind": "duration", "text": str(micros)}
        if id(item) in active:
            raise ValueError("property content cannot contain cycles")
        active.add(id(item))
        try:
            if typ in (list, tuple, set, frozenset):
                children = [visit(child) for child in item]
                if typ in (set, frozenset):
                    children.sort(key=lambda child: json.dumps(child, sort_keys=True))
                return {"kind": typ.__name__, "items": children}
            if typ in (dict, MappingProxyType):
                return {
                    "kind": "mapping_proxy" if typ is MappingProxyType else "mapping",
                    "entries": [
                        {"key": visit(key), "value": visit(child)}
                        for key, child in item.items()
                    ],
                }
            raise TypeError(f"unsupported property type: {typ.__name__}")
        finally:
            active.remove(id(item))

    return PropertyContent.from_data(visit(value))


def decode(content: PropertyContent) -> object:
    """Validate tagged content and return a detached Python representation."""

    def visit(data):
        kind = data["kind"]
        scalar = {
            "boolean",
            "integer",
            "float",
            "string",
            "uuid",
            "date",
            "datetime",
            "time",
            "duration",
        }
        allowed = {"kind"}
        if kind in scalar:
            allowed.add("text")
            if "text" not in data:
                raise ValueError(f"{kind} content requires text")
        elif kind in {"list", "tuple", "set", "frozenset"}:
            allowed.add("items")
            if not isinstance(data.get("items"), list):
                raise ValueError(f"{kind} content requires items")
        elif kind in {"mapping", "mapping_proxy"}:
            allowed.add("entries")
            if not isinstance(data.get("entries"), list):
                raise ValueError("mapping content requires entries")
        if kind in {"datetime", "time"}:
            allowed.update(("zone", "fold"))
        if set(data) - allowed:
            raise ValueError(f"unexpected fields in {kind} content")
        text = data.get("text")
        if kind == "null":
            return None
        if kind == "boolean":
            if text not in ("True", "False"):
                raise ValueError("invalid Boolean text")
            return text == "True"
        if kind == "integer":
            value = int(text)
            if str(value) != text:
                raise ValueError("integer text must be canonical")
            return value
        if kind == "float":
            value = float(text)
            if not math.isfinite(value) or repr(value) != text:
                raise ValueError("float text must be finite and canonical")
            return value
        if kind == "string":
            return text
        if kind == "uuid":
            return UUID(text)
        if kind == "date":
            return date.fromisoformat(text)
        if kind in {"datetime", "time"}:
            value = (datetime if kind == "datetime" else time).fromisoformat(text)
            if data.get("zone"):
                zoned = value.replace(
                    tzinfo=ZoneInfo(data["zone"]), fold=data.get("fold", 0)
                )
                if value.utcoffset() != zoned.utcoffset():
                    raise ValueError("timezone and encoded offset disagree")
                value = zoned
            return value.replace(fold=data.get("fold", 0))
        if kind == "duration":
            return timedelta(microseconds=int(text))
        if kind in {"list", "tuple", "set", "frozenset"}:
            items = [visit(child) for child in data["items"]]
            result = {"list": list, "tuple": tuple, "set": set, "frozenset": frozenset}[
                kind
            ](items)
            if kind in {"set", "frozenset"} and len(result) != len(items):
                raise ValueError("duplicate set member")
            return result
        if kind in {"mapping", "mapping_proxy"}:
            result = {}
            for entry in data["entries"]:
                key = visit(entry["key"])
                if key in result:
                    raise ValueError("duplicate mapping key")
                result[key] = visit(entry["value"])
            return MappingProxyType(result) if kind == "mapping_proxy" else result
        raise ValueError(f"unsupported content kind: {kind}")

    try:
        return visit(content.to_data())
    except (LookupError, OverflowError) as error:
        raise ValueError(f"invalid property content: {error}") from error


def validate_content(content: PropertyContent) -> None:
    """Check conditional shape and scalar meaning beyond structural validation."""
    decode(content)
