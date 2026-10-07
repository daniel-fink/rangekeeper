"""Schema-directed, revision-local declaration and ownership indexes.

Only embedded record slots are traversed. References are not followed and opaque
Claim content is never mistaken for a declaration merely because it contains `id`.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeVar
from uuid import UUID

from ._records import Record
from ._schema.validation import _slot_map
from .errors import IdentityConflictError, MissingReferenceError, ReferenceTypeError
from .validate import require_uuid

R = TypeVar("R", bound=Record)


def walk(
    record: Record,
    owner: UUID | None = None,
    path: str = "",
) -> Iterator[tuple[Record, UUID | None, str]]:
    """Yield embedded records in document encounter order with nearest identified owner."""
    yield record, owner, path
    fields = _slot_map(record._kind)
    if "id" in fields:
        owner = getattr(record, "id")
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
        records, owners, paths = {}, {}, {}
        for record, owner, path in walk(root):
            if "id" not in _slot_map(record._kind):
                continue
            identity = getattr(record, "id")
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
            else enumerate(value) if field["many"] else ((None, value),)
        )
        for index, child in items:
            if isinstance(child, Mapping):
                location = (
                    path
                    + "/"
                    + name.replace("~", "~0").replace("/", "~1")
                    + (
                        "/" + str(index).replace("~", "~0").replace("/", "~1")
                        if index is not None
                        else ""
                    )
                )
                yield from walk_data(kinds[0], child, location)
