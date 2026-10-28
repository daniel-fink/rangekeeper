"""Explicit complete-section replacement for atomic Model revision construction."""

from dataclasses import dataclass

from rangekeeper.schema.records import (
    _TYPES,
    Definitions,
    Geometry,
    Metadata,
    Provenance,
    System,
)
from rangekeeper.schema.runtime import UNSET, Unset
from rangekeeper.schema.validation import slots_for

# The record type of each Model slot. Each slot except metadata is a section.
_FIELDS = {
    name: _TYPES[slot["options"][0]["kind"]]
    for name, slot in slots_for("Model").items()
}
SECTIONS = tuple(name for name in _FIELDS if name != "metadata")


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
    geometry: Geometry | Unset = UNSET
    metadata: Metadata | Unset = UNSET

    def __post_init__(self) -> None:
        for name, kind in _FIELDS.items():
            value = getattr(self, name)
            if value is not UNSET and not isinstance(value, kind):
                raise TypeError(f"{name} must be {kind.__name__} or omitted")
