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
    ContractError,
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

    def missing() -> MissingReferenceError:
        return MissingReferenceError(
            path, kind="record", by="path", where=root_name(root)
        )

    if not isinstance(path, str):
        raise TypeError("path must be a string")
    if path == "":
        return RecordLocation(root, None, path)
    if not path.startswith("/") or re.search(r"~(?![01])", path):
        raise ContractError(
            "path must be a canonical JSON pointer", values={"path": path}
        )
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
            raise missing()
        kind = next(
            (
                option["kind"]
                for option in field["options"]
                if option["category"] == "record"
            ),
            None,
        )
        if kind is None:
            raise missing()
        value = current._data[name]
        if field["many"]:
            if offset == len(tokens):
                raise missing()
            token = tokens[offset]
            offset += 1
            if re.fullmatch(r"0|[1-9][0-9]*", token) is None:
                raise ContractError(
                    "array indexes must be canonical nonnegative integers",
                    values={"path": path, "index": token},
                )
            if not isinstance(value, tuple):
                raise missing()
            # Compare decimal lengths before int conversion, including very long
            # input indexes. This also keeps missing indexes in the lookup family.
            last = str(len(value) - 1)
            if (
                not value
                or len(token) > len(last)
                or (len(token) == len(last) and token > last)
            ):
                raise missing()
            value = value[int(token)]
        if not isinstance(value, Mapping):
            raise missing()
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


def root_name(root: Record) -> str:
    """Name a root record for an error: its kind, and its UUID when it has one."""
    metadata = root._data.get("metadata")
    if isinstance(metadata, Mapping) and "id" in metadata:
        return f"{root._kind} {metadata['id']}"
    return root._kind


@dataclass(frozen=True, slots=True)
class RecordIndex:
    """Read-only acceleration structure derived from one validated root record.

    ``where`` names the root in the errors of ``get``.
    """

    records: Mapping[UUID, Record]
    owners: Mapping[UUID, UUID | None]
    paths: Mapping[UUID, str]
    where: str = ""

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
            MappingProxyType(records),
            MappingProxyType(owners),
            MappingProxyType(paths),
            root_name(root),
        )

    def get(self, identity: UUID, kind: type[R]) -> R:
        """Resolve exactly one UUID; never reinterpret a string as a code or name."""
        require_uuid(identity, "id")
        try:
            record = self.records[identity]
        except KeyError as error:
            raise MissingReferenceError(
                identity,
                kind="record" if kind is Record else kind.__name__,
                where=self.where or None,
            ) from error
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
