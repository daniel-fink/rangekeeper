"""Shared mechanics for generated records; field definitions live in LinkML."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import date as Date
from types import MappingProxyType
from typing import TypeAlias, TypeVar, cast
from uuid import UUID

FrozenJSONValue: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | Mapping[str, "FrozenJSONValue"]
    | tuple["FrozenJSONValue", ...]
)
JSONValue: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | Mapping[str, "JSONValue"]
    | list["JSONValue"]
    | tuple["JSONValue", ...]
)
from rangekeeper.schema.kinds import record_type  # noqa: E402

R = TypeVar("R", bound="Record")


class Unset:
    """Constructor sentinel distinguishing omission from explicit null."""

    __slots__ = ()


UNSET = Unset()


def copy_json(value, active=None):
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
            return {key: copy_json(child, active) for key, child in value.items()}
        if isinstance(value, (list, tuple)):
            return [copy_json(child, active) for child in value]
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
    from rangekeeper.schema.validation import _slot_map

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


def exact_equal(left, right) -> bool:
    """Compare JSON values with ordered collections and type-sensitive scalars."""
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return left.keys() == right.keys() and all(
            exact_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (tuple, list)) and isinstance(right, (tuple, list)):
        return len(left) == len(right) and all(
            map(lambda pair: exact_equal(*pair), zip(left, right, strict=True))
        )
    if type(left) is not type(right):
        return False
    if type(left) is float:
        return left == right and (
            left != 0 or math.copysign(1, left) == math.copysign(1, right)
        )
    return left == right


def comparison_data(kind: str, data: Mapping) -> dict:
    """Prepare schema equivalence without copying opaque content or changing records."""
    from rangekeeper.schema.validation import _slot_map

    result = dict(data)
    for name, field in _slot_map(kind).items():
        if name not in result or result[name] is None:
            continue

        def item(value):
            for option in field["options"]:
                if option["category"] in ("record", "keyed") and isinstance(
                    value, Mapping
                ):
                    return comparison_data(option["kind"], value)
            return value

        if field["mapping"]:
            result[name] = {key: item(child) for key, child in result[name].items()}
        elif field["many"]:
            children = [item(child) for child in result[name]]
            if not field["ordered"]:
                children.sort(
                    key=lambda child: json.dumps(
                        child,
                        sort_keys=True,
                        default=lambda value: (
                            dict(value) if isinstance(value, Mapping) else list(value)
                        ),
                    )
                )
            result[name] = children
        else:
            result[name] = item(result[name])
    return result


EMPTY: Mapping[str, FrozenJSONValue] = MappingProxyType({})


def _encode_uuid(value):
    return str(value) if isinstance(value, UUID) else copy_json(value)


def _encode_date(value):
    return value.isoformat() if type(value) is Date else copy_json(value)


def _encode_enum(value, enum, name):
    if value is None:
        return None
    if not isinstance(value, enum):
        raise TypeError(f"{name}: expected {enum.__name__}")
    return value.value


def _encode_record(value, cls, name):
    if isinstance(value, Record):
        if not isinstance(value, cls):
            raise TypeError(f"{name}: incompatible record {value._kind}")
        # The frozen tree is copied once, by _set_data.
        return value._data
    return copy_json(value)


def _encode_many(value, encode):
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    return encode(value)


def _decode_uuid(value):
    return UUID(value) if isinstance(value, str) else value


def _decode_uuids(values):
    if values is None:
        return None
    return tuple(UUID(v) if isinstance(v, str) else v for v in values)


def _decode_enum(value, enum):
    return None if value is None else enum(value)


def _decode_date(value):
    if isinstance(value, str):
        try:
            return Date.fromisoformat(value)
        except ValueError:
            return value
    return value


def _decode_dates(values):
    return None if values is None else tuple(_decode_date(v) for v in values)


def _borrow(cls, data):
    """Return a record of ``cls`` that shares an already validated frozen tree."""
    record = cls.__new__(cls)
    object.__setattr__(record, "_data", data)
    return record


class Record:
    """Immutable schema record. Constructors check structure, not cross-record semantics."""

    __slots__ = ("_data", "_cache")
    _kind: str
    _SLOTS: Mapping[str, Mapping]
    _data: Mapping[str, FrozenJSONValue]
    _cache: dict[str, object]

    def __new__(cls, *args, **kwargs):
        """Create an instance of the registered owner class of this kind."""
        owner = record_type(cls._kind)
        return object.__new__(owner if issubclass(owner, cls) else cls)

    def __setattr__(self, name, value):
        raise AttributeError("records are immutable")

    def __delattr__(self, name):
        raise AttributeError("records are immutable")

    def _encode_field(self, name: str, value: object) -> object:
        """Encode one union field; generated code encodes every other field."""
        from rangekeeper.schema.enums import _ENUM_TYPES
        from rangekeeper.schema.records import _TYPES
        from rangekeeper.schema.validation import _slot_map

        meta = _slot_map(self._kind)[name]

        def encode(item):
            enum = next((o for o in meta["options"] if o["category"] == "enum"), None)
            if enum is not None and item is not None:
                expected = _ENUM_TYPES[enum["kind"]]
                if not isinstance(item, expected):
                    raise TypeError(f"{name}: expected {expected.__name__}")
                return item.value
            if isinstance(item, Record):
                if not any(
                    o["category"] == "record" and isinstance(item, _TYPES[o["kind"]])
                    for o in meta["options"]
                ):
                    raise TypeError(f"{name}: incompatible record {item._kind}")
                return item._data
            if isinstance(item, UUID) and any(
                o["category"] == "uuid" for o in meta["options"]
            ):
                return str(item)
            if type(item) is Date and any(
                o["category"] == "primitive" and o["kind"] == "date"
                for o in meta["options"]
            ):
                return item.isoformat()
            return copy_json(item)

        if meta["many"] and isinstance(value, (tuple, list)):
            return [encode(item) for item in value]
        return encode(value)

    def _replace(self: R, fields: Mapping[str, object]) -> R:
        """Copy encoded fields without collapsing omitted, null and empty values.

        Generated signatures provide field types and reject unknown keywords. This
        primitive changes content only; document revision rules belong to facades.
        """
        data: dict[str, object] = dict(self._data)
        data.update(fields)
        return type(self).from_data(data)

    def _set_data(self, data: object) -> None:
        from rangekeeper.schema.validation import _validate_json

        if hasattr(self, "_data"):
            raise AttributeError("records are already initialized")
        data = copy_json(data)
        _validate_json(self._kind, data).raise_if_invalid()
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
        from rangekeeper.shared.encoding import parse_json

        return cls.from_data(cast(Mapping[str, object], parse_json(text)))

    def to_data(self) -> dict[str, object]:
        """Export a detached JSON-compatible tree, retaining omitted/null/empty fields."""
        return copy_json(self._data)

    def has_field(self, name: str) -> bool:
        """Return whether a field is present; raise KeyError for an unknown field."""
        from rangekeeper.schema.validation import _slot_map

        if name not in _slot_map(self._kind):
            raise KeyError(name)
        return name in self._data

    def field_names(self) -> tuple[str, ...]:
        """Return present serialized field names in encounter order, without copying values.

        Schema-driven visitors use this with generated properties. Omitted fields
        are excluded; explicit null/empty fields remain present.
        """
        return tuple(self._data)

    def _child(self, name: str, cls: type[Record], many: bool) -> object:
        """Decode a record field once; later reads return the cached children."""
        try:
            cache = self._cache
        except AttributeError:
            cache = {}
            object.__setattr__(self, "_cache", cache)
        if name in cache:
            return cache[name]
        if name not in self._data:
            result: object = () if many else None
        else:
            value = self._data[name]
            if value is None:
                result = None
            elif many:
                result = tuple(
                    _borrow(cls, item) if isinstance(item, Mapping) else item
                    for item in cast(tuple, value)
                )
            else:
                result = _borrow(cls, value) if isinstance(value, Mapping) else value
        cache[name] = result
        return result

    def _field(self, name):
        """Decode one union field; generated properties decode every other field."""
        from rangekeeper.schema.enums import _ENUM_TYPES
        from rangekeeper.schema.records import _TYPES
        from rangekeeper.schema.validation import _slot_map

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
                if option["category"] == "enum":
                    return _ENUM_TYPES[option["kind"]](item)
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

    def equivalent(self, other: object) -> bool:
        """Compare schema content, ignoring only declared unordered collection order."""
        return (
            isinstance(other, Record)
            and type(self) is type(other)
            and exact_equal(
                comparison_data(self._kind, self._data),
                comparison_data(other._kind, other._data),
            )
        )

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Record)
            and type(self) is type(other)
            and exact_equal(self._data, other._data)
        )

    # Python's standard unhashable marker; mypy models object.__hash__ as callable.
    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"{type(self).__name__}.from_data({self.to_data()!r})"
