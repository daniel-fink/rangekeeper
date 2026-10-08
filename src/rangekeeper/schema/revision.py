"""Shared document revision identity, lineage and meaningful-change requirements."""

from typing import TYPE_CHECKING

from rangekeeper.schema.runtime import comparison_data, exact_equal
from rangekeeper.shared.errors import RevisionConflictError, UnsupportedVersionError

if TYPE_CHECKING:
    from rangekeeper.schema.records import Model, Specification


def check_revision(
    before: "Model | Specification",
    after: "Model | Specification",
) -> None:
    """Require new lineage and a meaningful change, without migrating the schema.

    Both document facades use the same identity and comparison rules. Construction
    still validates the complete candidate in its own domain before publication.
    """
    if type(before) is not type(after):
        raise TypeError("a revision must retain its document kind")
    old, new = before.metadata, after.metadata
    if new.id in (old.id, old.previous) or new.previous != old.id:
        raise RevisionConflictError(
            "new metadata must not reuse this revision or its predecessor, and must set previous=current UUID"
        )
    if new.schema_version != old.schema_version:
        raise UnsupportedVersionError("revise cannot migrate schema versions")
    left, right = comparison_data(before._kind, before._data), comparison_data(
        after._kind, after._data
    )
    for data, metadata in ((left, old), (right, new)):
        data["metadata"] = {
            key: value
            for key, value in metadata._data.items()
            if key not in ("id", "previous")
        }
    if exact_equal(left, right):
        raise RevisionConflictError(
            "replacement changes no domain or descriptive content"
        )
