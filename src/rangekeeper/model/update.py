"""Explicit complete-section replacement for atomic Model revision construction."""

from dataclasses import dataclass

from rangekeeper.schema.runtime import UNSET, Unset
from rangekeeper.schema.records import Definitions, Metadata, Provenance, System


@dataclass(frozen=True, slots=True, kw_only=True)
class Update:
    """A Python operation request, not a second serialized Model schema.

    Omitted sections are retained. Empty generated containers clear their contents;
    references are never silently repaired or cascaded. Supplying metadata means
    supplying a new revision UUID and an explicit previous=current UUID.
    """

    definitions: Definitions | Unset = UNSET
    system: System | Unset = UNSET
    provenance: Provenance | Unset = UNSET
    metadata: Metadata | Unset = UNSET

    def __post_init__(self) -> None:
        for name, kind in (
            ("definitions", Definitions),
            ("system", System),
            ("provenance", Provenance),
            ("metadata", Metadata),
        ):
            value = getattr(self, name)
            if value is not UNSET and not isinstance(value, kind):
                raise TypeError(f"{name} must be {kind.__name__} or omitted")
