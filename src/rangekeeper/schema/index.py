"""Schema-directed, revision-local declaration and ownership indexes.

Only embedded record slots are traversed. References are not followed and opaque
Claim content is never mistaken for a declaration merely because it contains `id`.
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeVar, cast
from uuid import UUID

from rangekeeper.schema.runtime import Record
from rangekeeper.schema.validation import _slot_map
from rangekeeper.shared import pointer
from rangekeeper.shared.arguments import require_uuid
from rangekeeper.shared.errors import (
    IdentityConflictError,
    MissingReferenceError,
    ReferenceTypeError,
)

R = TypeVar("R", bound=Record)


@dataclass(frozen=True, slots=True)
class RecordLocation:
    """One immutable embedded record, its nearest identified owner and original path."""

    record: Record
    owner_id: UUID | None
    path: str


def record_at(root: Record, path: str) -> RecordLocation:
    """Resolve one canonical walker path without decoding unselected siblings.

    The root is already validated and frozen. Only declared embedded records are
    eligible; UUID references, keyed values and opaque content are not records.
    Pointer parsing takes work proportional to its length; selection visits only
    the requested chain and creates at most one borrowed wrapper per record.
    """
    from rangekeeper.schema.records import _TYPES

    if not isinstance(path, str):
        raise TypeError("path must be a string")
    if path == "":
        return RecordLocation(root, None, path)
    if not path.startswith("/") or re.search(r"~(?![01])", path):
        raise ValueError("path must be a canonical JSON pointer")
    tokens = path[1:].split("/")
    current = root
    owner: UUID | None = None
    offset = 0
    while offset < len(tokens):
        fields = _slot_map(current._kind)
        if "id" in fields:
            owner = current.id  # type: ignore[attr-defined]  # an "id" slot
        name = tokens[offset]
        offset += 1
        # walk emits schema slot names verbatim. Do not introduce pointer aliases.
        field = fields.get(name)
        if field is None or field["mapping"] or name not in current._data:
            raise MissingReferenceError(path)
        kind = next(
            (
                option["kind"]
                for option in field["options"]
                if option["category"] == "record"
            ),
            None,
        )
        if kind is None:
            raise MissingReferenceError(path)
        value = current._data[name]
        if field["many"]:
            if offset == len(tokens):
                raise MissingReferenceError(path)
            token = tokens[offset]
            offset += 1
            if re.fullmatch(r"0|[1-9][0-9]*", token) is None:
                raise ValueError("array indexes must be canonical nonnegative integers")
            if not isinstance(value, tuple):
                raise MissingReferenceError(path)
            # Compare decimal lengths before int conversion, including very long
            # input indexes. This also keeps missing indexes in the lookup family.
            last = str(len(value) - 1)
            if (
                not value
                or len(token) > len(last)
                or (len(token) == len(last) and token > last)
            ):
                raise MissingReferenceError(path)
            value = value[int(token)]
        if not isinstance(value, Mapping):
            raise MissingReferenceError(path)
        # Match Record._field's record branch, borrowing only this frozen child.
        cls = cast(type[Record], _TYPES[kind])
        current = cls.__new__(cls)
        object.__setattr__(current, "_data", value)
    return RecordLocation(current, owner, path)


def walk(
    record: Record,
    owner: UUID | None = None,
    path: str = "",
) -> Iterator[tuple[Record, UUID | None, str]]:
    """Yield embedded records in document encounter order with nearest identified owner."""
    yield record, owner, path
    fields = _slot_map(record._kind)
    if "id" in fields:
        owner = record.id  # type: ignore[attr-defined]  # an "id" slot
    for name in record.field_names():
        field = fields[name]
        if not any(option["category"] == "record" for option in field["options"]):
            continue
        value = getattr(record, name)
        if isinstance(value, Record):
            yield from walk(value, owner, path + "/" + name)
        elif isinstance(value, tuple):
            for index, child in enumerate(value):
                if isinstance(child, Record):
                    yield from walk(child, owner, f"{path}/{name}/{index}")


@dataclass(frozen=True, slots=True)
class RecordIndex:
    """Read-only acceleration structure derived from one validated root record."""

    records: Mapping[UUID, Record]
    owners: Mapping[UUID, UUID | None]
    paths: Mapping[UUID, str]

    @classmethod
    def build(cls, root: Record) -> "RecordIndex":
        """Index each identified record under one root; reject duplicate UUIDs."""
        records, owners, paths = {}, {}, {}
        for record, owner, path in walk(root):
            if "id" not in _slot_map(record._kind):
                continue
            identity = record.id  # type: ignore[attr-defined]  # an "id" slot
            if identity in records:
                raise IdentityConflictError(f"duplicate declaration UUID: {identity}")
            records[identity], owners[identity], paths[identity] = record, owner, path
        return cls(
            MappingProxyType(records), MappingProxyType(owners), MappingProxyType(paths)
        )

    def get(self, identity: UUID, kind: type[R]) -> R:
        """Resolve exactly one UUID; never reinterpret a string as a code or name."""
        require_uuid(identity, "id")
        try:
            record = self.records[identity]
        except KeyError as error:
            raise MissingReferenceError(str(identity)) from error
        if not isinstance(record, kind):
            raise ReferenceTypeError(
                f"{identity} is {type(record).__name__}, expected {kind.__name__}"
            )
        return record


def walk_data(kind: str, data: Mapping, path: str = ""):
    """Visit already checked wire records through the same schema slots as walk."""
    yield data, path
    fields = _slot_map(kind)
    for name, value in data.items():
        field = fields[name]
        if value is None:
            continue
        kinds = [
            option["kind"]
            for option in field["options"]
            if option["category"] in ("record", "keyed")
        ]
        if not kinds:
            continue
        items = (
            value.items()
            if field["mapping"]
            else enumerate(value)
            if field["many"]
            else ((None, value),)
        )
        for index, child in items:
            if isinstance(child, Mapping):
                location = pointer.child(
                    path, name, *(() if index is None else (index,))
                )
                yield from walk_data(kinds[0], child, location)
