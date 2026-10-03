"""Small declaration primitives shared by direct APIs and YAML requests."""

from collections.abc import Mapping
from datetime import date, datetime, time
from uuid import UUID


def fields(value, allowed, required=()):
    if not isinstance(value, Mapping):
        raise TypeError("Expected a mapping")
    if set(value) - set(allowed):
        raise ValueError(f"Unknown fields: {sorted(set(value) - set(allowed))}")
    if set(required) - set(value):
        raise ValueError(f"Missing fields: {sorted(set(required) - set(value))}")
    return dict(value)


def text(value):
    if type(value) is not str or not value.strip():
        raise ValueError("Expected nonempty text")
    return value


def sequence(value):
    if not isinstance(value, (tuple, list)):
        raise TypeError("Expected an ordered sequence")
    return tuple(value)


def plain(value):
    if isinstance(value, UUID):
        return {"uuid": str(value)}
    if isinstance(value, (datetime, date, time)):
        return {type(value).__name__: value.isoformat()}
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [plain(x) for x in value]
    if hasattr(value, "to_mapping"):
        return plain(value.to_mapping())
    return value
