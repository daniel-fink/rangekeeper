"""Shared mechanics for generated records; field definitions live in LinkML."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from datetime import date as Date
from decimal import Decimal
from difflib import get_close_matches
from functools import cache
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
from rangekeeper.shared import amounts as _amounts  # noqa: E402
from rangekeeper.shared.errors import MissingReferenceError  # noqa: E402

R = TypeVar("R", bound="Record")


class Unset:
    """Constructor sentinel distinguishing omission from explicit null."""

    __slots__ = ()


UNSET = Unset()


class Omit:
    """Replacement sentinel that removes an optional field."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "OMIT"


OMIT = Omit()


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
        return value._data
    if isinstance(value, Mapping):
        # Data, not a record: validate it in full once.
        return cls.from_data(value)._data
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


def _number(value) -> bool:
    """Match JSON Schema ``number``: an int or float, not a bool."""
    return type(value) in (int, float)


def _integer(value) -> bool:
    """Match JSON Schema ``integer``, which includes an integral float."""
    return type(value) is int or type(value) is float and value.is_integer()


def _array(value) -> bool:
    return type(value) in (list, tuple)


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)


def _date(value: str) -> bool:
    """Match the jsonschema ``date`` format check."""
    try:
        return bool(_DATE.fullmatch(value) and Date.fromisoformat(value))
    except ValueError:
        return False


def _datetime(value: str) -> bool:
    """Match the jsonschema ``date-time`` format check (RFC 3339)."""
    # rfc3339-validator ships no type information.
    from rfc3339_validator import (  # type: ignore[import-untyped, unused-ignore]
        validate_rfc3339,
    )

    return bool(validate_rfc3339(value.upper()))


def _raise_issues(issues) -> None:
    """Raise ValidationError for node check issues; return when there are none."""
    if issues:
        from rangekeeper.shared.diagnostics import Issue, ValidationReport

        ValidationReport(
            tuple(Issue(code, message, path=path) for code, message, path in issues)
        ).raise_if_invalid()


def _require_invariants(record, path: str) -> None:
    """Run the local rules of a value type; report a failure as a ValidationError."""
    if type(record)._invariants is Record._invariants:
        return
    try:
        record._invariants()
    except ValueError as error:
        from rangekeeper.shared.codes import Code
        from rangekeeper.shared.diagnostics import Issue, ValidationReport

        # A rule with its own code, such as currency_amount, names it.
        code = getattr(error, "code", None) or Code(f"invariant.{record._kind}")
        ValidationReport((Issue(code, str(error), path=path),)).raise_if_invalid()


@cache
def _reaches_invariants(kind: str) -> bool:
    """Return whether a record of ``kind`` can contain a value type with rules."""
    from rangekeeper.schema.kinds import record_type
    from rangekeeper.schema.records import _TYPES
    from rangekeeper.schema.validation import _slot_map

    seen, pending = set(), [kind]
    while pending:
        current = pending.pop()
        if current in seen or current not in _TYPES:
            continue
        seen.add(current)
        if record_type(current)._invariants is not Record._invariants:
            return True
        for field in _slot_map(current).values():
            pending += [
                o["kind"]
                for o in field["options"]
                if o["category"] in ("record", "keyed")
            ]
    return False


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

    def _invariants(self) -> None:
        """Raise ValueError when a value type's local rules are not met.

        Owners of value types override this (ADR-011). Construction, replace
        and from_data run it; a decoded child of a checked record does not.
        """

    @classmethod
    def _coerce(cls, data: dict[str, object]) -> dict[str, object]:
        """Return encoded fields after a conversion that depends on other fields.

        Construction and replace call it before the node check. Owners of value
        types override it: a currency amount depends on its units (ADR-023).
        ``from_data`` does not call it; serialized data is already exact.
        """
        return data

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
            records = [o for o in meta["options"] if o["category"] == "record"]
            if isinstance(item, Record):
                if not any(isinstance(item, _TYPES[o["kind"]]) for o in records):
                    raise TypeError(f"{name}: incompatible record {item._kind}")
                return item._data
            if isinstance(item, Mapping) and records:
                # A slot has at most one record type (see check_slots).
                return _TYPES[records[0]["kind"]].from_data(item)._data
            if isinstance(item, UUID) and any(
                o["category"] == "uuid" for o in meta["options"]
            ):
                return str(item)
            if type(item) is Date and any(
                o["category"] == "primitive" and o["kind"] == "date"
                for o in meta["options"]
            ):
                return item.isoformat()
            if type(item) in (Decimal, str) and any(
                o["category"] == "primitive" and o["kind"] == "Amount"
                for o in meta["options"]
            ):
                # Decimal text is exact; other text keeps its value and fails
                # the check, as does a Decimal that is not finite.
                if type(item) is str:
                    return _amounts.canonical(item) or item
                return _amounts.text(item) if item.is_finite() else str(item)
            return copy_json(item)

        if meta["many"] and isinstance(value, (tuple, list)):
            return [encode(item) for item in value]
        return encode(value)

    def _replace(self: R, fields: Mapping[str, object]) -> R:
        """Copy encoded fields without collapsing omitted, null and empty values.

        Only this record is checked: its changed fields and its rules. Unchanged
        fields and child records keep their frozen, already checked content.
        Generated signatures provide field types and reject unknown keywords.
        Document revision rules belong to facades.
        """
        from rangekeeper.schema.checks import CHECKS
        from rangekeeper.schema.validation import _slot_map, _validate_json

        data: dict[str, object] = dict(self._data)
        for name, value in fields.items():
            if value is OMIT:
                data.pop(name, None)
            else:
                data[name] = value
        coerced = type(self)._coerce(data)
        if coerced is not data:
            fields = {
                **fields,
                **{n: v for n, v in coerced.items() if data.get(n, OMIT) is not v},
            }
            data = coerced
        slots = _slot_map(self._kind)
        if any(slots[name]["mapping"] for name in fields):
            # A keyed collection holds reduced child records that only the
            # JSON Schema describes.
            _validate_json(self._kind, copy_json(data)).raise_if_invalid()
        else:
            _raise_issues(CHECKS[self._kind](data, fields))
        changed = {name: data[name] for name in fields if name in data}
        data.update(_freeze(_normalize(self._kind, changed)))
        result = _borrow(type(self), MappingProxyType(data))
        _require_invariants(result, "")
        return result

    def _set_checked(self, data: dict[str, object]) -> None:
        """Set encoded constructor fields after the node check of this record.

        The generated encoders copy each argument, and child records are already
        checked, so the tree is not copied or validated again. A keyed
        collection uses jsonschema, as in replace.
        """
        from rangekeeper.schema.checks import CHECKS
        from rangekeeper.schema.validation import _slot_map, _validate_json

        if hasattr(self, "_data"):
            raise AttributeError("records are already initialized")
        data = type(self)._coerce(data)
        slots = _slot_map(self._kind)
        if any(slots[name]["mapping"] for name in data):
            _validate_json(self._kind, copy_json(data)).raise_if_invalid()
        else:
            _raise_issues(CHECKS[self._kind](data))
        object.__setattr__(self, "_data", _freeze(_normalize(self._kind, data)))
        _require_invariants(self, "")

    def _set_data(self, data: object) -> None:
        """Copy, validate with jsonschema and freeze untrusted data."""
        from rangekeeper.schema.validation import _validate_json, detached

        if hasattr(self, "_data"):
            raise AttributeError("records are already initialized")
        data = detached(data)
        _validate_json(self._kind, data).raise_if_invalid()
        object.__setattr__(self, "_data", _freeze(_normalize(self._kind, data)))
        if _reaches_invariants(self._kind):
            from rangekeeper.schema.index import walk

            # Children first, so the most specific rule reports a failure.
            for record, _, path in reversed(list(walk(self))):
                _require_invariants(record, path)

    @classmethod
    def from_data(cls: type[R], data: Mapping[str, object]) -> R:
        """Validate and copy serialized data; normalize schema-declared UUIDs.

        Data that is not JSON, such as a ``date`` or a non-finite number,
        raises ``ValidationError`` with ``Code.STRUCTURE_JSON``.
        """
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
        """Return whether a field is present.

        A name that is not a field of this kind raises ``MissingReferenceError``
        with the nearest field names.
        """
        from rangekeeper.schema.validation import _slot_map

        fields = _slot_map(self._kind)
        if name not in fields:
            raise MissingReferenceError(
                name,
                kind="field",
                by="name",
                where=self._kind,
                candidates=get_close_matches(str(name), sorted(fields), n=3),
            )
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
                if (
                    option["category"] == "primitive"
                    and option["kind"] == "Amount"
                    and type(item) is str
                ):
                    return Decimal(item)
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
        """Return a one-line summary; ``to_data`` gives the complete content."""
        parts = []
        for name, value in self._data.items():
            if isinstance(value, Mapping):
                text = "{...}"
            elif isinstance(value, tuple):
                text = f"[{len(value)}]"
            else:
                text = repr(value)
                if len(text) > 40:
                    text = text[:37] + "..."
            parts.append(f"{name}={text}")
        summary = ", ".join(parts)
        if len(summary) > 160:
            summary = summary[:157] + "..."
        return f"{type(self).__name__}({summary})"
