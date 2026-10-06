"""Shared mechanics for generated records; field definitions live in LinkML."""

from __future__ import annotations

from collections.abc import Mapping
import json
import math
from types import MappingProxyType
from typing import TypeAlias, TypeVar, Union
from uuid import UUID
from datetime import date as Date

FrozenJSONValue: TypeAlias = Union[
    None,
    bool,
    int,
    float,
    str,
    Mapping[str, "FrozenJSONValue"],
    tuple["FrozenJSONValue", ...],
]
JSONValue: TypeAlias = Union[
    None,
    bool,
    int,
    float,
    str,
    Mapping[str, "JSONValue"],
    list["JSONValue"],
    tuple["JSONValue", ...],
]
R = TypeVar("R", bound="Record")


class Unset:
    """Constructor sentinel distinguishing omission from explicit null."""

    __slots__ = ()


UNSET = Unset()


def _json_copy(value, active=None):
    """Copy strictly JSON-compatible data, rejecting cycles and non-finite numbers."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite number is not JSON")
        return value
    if active is None:
        active = set()
    if id(value) in active:
        raise ValueError("cyclic data is not JSON")
    active.add(id(value))
    try:
        if isinstance(value, Mapping):
            if any(type(key) is not str for key in value):
                raise TypeError("JSON object keys must be strings")
            return {key: _json_copy(child, active) for key, child in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_copy(child, active) for child in value]
        raise TypeError(f"unsupported JSON value: {type(value).__name__}")
    finally:
        active.remove(id(value))


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


def _normalize(kind, data):
    """Normalize only schema-declared UUID slots, never opaque content."""
    from ._schema.validation import _slot_map

    result = dict(data)
    for name, meta in _slot_map(kind).items():
        if name not in result or result[name] is None:
            continue

        def item(value):
            for option in meta["options"]:
                if option["category"] == "uuid" and isinstance(value, str):
                    return str(UUID(value))
                if option["category"] in ("record", "keyed") and isinstance(
                    value, dict
                ):
                    return _normalize(option["kind"], value)
            return value

        if meta["mapping"]:
            result[name] = {key: item(value) for key, value in result[name].items()}
        else:
            result[name] = (
                [item(v) for v in result[name]] if meta["many"] else item(result[name])
            )
    return result


class Record:
    """Immutable schema record. Constructors check structure, not cross-record semantics."""

    __slots__ = ("_data",)
    _kind: str
    _data: Mapping[str, FrozenJSONValue]

    def __setattr__(self, name, value):
        raise AttributeError("records are immutable")

    def __delattr__(self, name):
        raise AttributeError("records are immutable")

    def _initialize(self, fields: Mapping[str, object]) -> None:
        from ._schema.records import _TYPES
        from ._schema.validation import _slot_map

        slots = _slot_map(self._kind)
        data = {}
        for name, value in fields.items():
            if value is UNSET:
                continue
            meta = slots[name]

            def encode(item):
                if isinstance(item, Record):
                    if not any(
                        o["category"] == "record"
                        and isinstance(item, _TYPES[o["kind"]])
                        for o in meta["options"]
                    ):
                        raise TypeError(f"{name}: incompatible record {item._kind}")
                    return item.to_data()
                if isinstance(item, UUID) and any(
                    o["category"] == "uuid" for o in meta["options"]
                ):
                    return str(item)
                if type(item) is Date and any(
                    o["category"] == "primitive" and o["kind"] == "date"
                    for o in meta["options"]
                ):
                    return item.isoformat()
                return _json_copy(item)

            data[name] = (
                [encode(item) for item in value]
                if meta["many"] and isinstance(value, (tuple, list))
                else encode(value)
            )
        self._set_data(data)

    def _set_data(self, data: object) -> None:
        from ._schema.validation import validate

        if hasattr(self, "_data"):
            raise AttributeError("records are already initialized")
        data = _json_copy(data)
        validate(self._kind, data).raise_if_invalid()
        object.__setattr__(self, "_data", _freeze(_normalize(self._kind, data)))

    @classmethod
    def from_data(cls: type[R], data: Mapping[str, object]) -> R:
        """Validate and copy serialized data; normalize schema-declared UUIDs."""
        record = cls.__new__(cls)
        record._set_data(data)
        return record

    @classmethod
    def from_json(cls: type[R], text: str) -> R:
        """Read one JSON record, rejecting duplicate object keys at every depth."""

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON key: {key}")
                result[key] = value
            return result

        return cls.from_data(json.loads(text, object_pairs_hook=unique))

    def to_data(self) -> dict[str, object]:
        """Export a detached JSON-compatible tree, retaining omitted/null/empty fields."""
        return _json_copy(self._data)

    def has_field(self, name: str) -> bool:
        from ._schema.validation import _slot_map

        if name not in _slot_map(self._kind):
            raise KeyError(name)
        return name in self._data

    def field_names(self) -> tuple[str, ...]:
        """Return present serialized field names in encounter order, without copying values.

        Schema-driven visitors use this with generated properties. Omitted fields
        are excluded; explicit null/empty fields remain present.
        """
        return tuple(self._data)

    def _field(self, name):
        from ._schema.records import _TYPES
        from ._schema.validation import _slot_map

        meta = _slot_map(self._kind)[name]
        if name not in self._data:
            if meta["mapping"]:
                return MappingProxyType({})
            return () if meta["many"] else None
        value = self._data[name]
        if value is None:
            return None
        if meta["mapping"]:
            return value

        def decode(item):
            for option in meta["options"]:
                if option["category"] == "uuid" and isinstance(item, str):
                    return UUID(item)
                if (
                    option["category"] == "primitive"
                    and option["kind"] == "date"
                    and isinstance(item, str)
                ):
                    # A schema union can also admit a timestamp string. Decode
                    # only the date branch; retain other validated alternatives.
                    try:
                        return Date.fromisoformat(item)
                    except ValueError:
                        continue
                if option["category"] == "record" and isinstance(item, Mapping):
                    cls = _TYPES[option["kind"]]
                    record = cls.__new__(cls)
                    object.__setattr__(record, "_data", item)
                    return record
            return item

        return tuple(decode(item) for item in value) if meta["many"] else decode(value)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Record)
            and type(self) is type(other)
            and json.dumps(self.to_data(), sort_keys=True)
            == json.dumps(other.to_data(), sort_keys=True)
        )

    # Python's standard unhashable marker; mypy models object.__hash__ as callable.
    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"{type(self).__name__}.from_data({self.to_data()!r})"
