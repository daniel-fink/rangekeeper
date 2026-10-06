"""Schema-directed, revision-local declaration and ownership indexes.

Only embedded record slots are traversed. References are not followed and opaque
Claim content is never mistaken for a declaration merely because it contains `id`.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeVar
from uuid import UUID

from .._records import Record
from .._schema.validation import _slot_map
from ..errors import IdentityConflictError, MissingReferenceError, ReferenceTypeError
from ..validate import require_uuid

R = TypeVar("R", bound=Record)


def walk(
    record: Record, owner: UUID | None = None, path: str = ""
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
class Index:
    """Read-only acceleration structure derived from one validated root record."""

    records: Mapping[UUID, Record]
    owners: Mapping[UUID, UUID | None]

    @classmethod
    def build(cls, root: Record) -> "Index":
        records, owners = {}, {}
        for record, owner, _ in walk(root):
            if "id" not in _slot_map(record._kind):
                continue
            identity = getattr(record, "id")
            if identity in records:
                raise IdentityConflictError(f"duplicate declaration UUID: {identity}")
            records[identity], owners[identity] = record, owner
        return cls(MappingProxyType(records), MappingProxyType(owners))

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

    def check_known_references(self, root: Record) -> None:
        """Check locally resolvable reference types without requiring external targets.

        Partial Specifications can point outside their declaration scope. A target
        already declared locally cannot masquerade as another record kind.
        Complete Model/composition validation owns reference existence checks.
        """
        from .._schema.records import _TYPES, Reference, Value, Movement

        for record, _, path in walk(root):
            for name, field in _slot_map(record._kind).items():
                types = tuple(
                    _TYPES[option["kind"]]
                    for option in field["options"]
                    if option["category"] == "uuid" and option["kind"] in _TYPES
                )
                if isinstance(record, Reference) and name == "target":
                    types = (Value, Movement)
                if not types:
                    continue
                value = getattr(record, name)
                for identity in value if isinstance(value, tuple) else (value,):
                    if isinstance(identity, UUID) and identity in self.records:
                        if not isinstance(self.records[identity], types):
                            raise ReferenceTypeError(
                                f"{path}/{name}: {identity} has the wrong local record kind"
                            )
