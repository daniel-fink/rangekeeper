"""Representation comparison guided by generated ordering annotations.

Only schema-declared unordered collections are sorted. Opaque content, ordered
mathematics and null/omitted/empty distinctions retain their supplied meaning.
"""

import json
from typing import TYPE_CHECKING

from ._records import _json_copy
from ._schema.validation import slots_for
from .errors import RevisionConflictError, UnsupportedVersionError

if TYPE_CHECKING:
    from ._schema.records import Model, Specification


def check_revision(
    before: "Model | Specification", after: "Model | Specification"
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
    left, right = before.to_data(), after.to_data()
    for data, metadata in ((left, old), (right, new)):
        data["metadata"] = {
            key: value
            for key, value in metadata.to_data().items()
            if key not in ("id", "previous")
        }
    if canonical(before._kind, left) == canonical(after._kind, right):
        raise RevisionConflictError(
            "replacement changes no domain or descriptive content"
        )


def canonical(kind: str, data: dict) -> str:
    """Return a stable comparison key, not an interchange encoding or content hash."""

    def visit(record_kind, value):
        result = _json_copy(value)
        for name, field in slots_for(record_kind).items():
            if name not in result or result[name] is None:
                continue

            def item(child):
                for option in field["options"]:
                    if option["category"] in ("record", "keyed") and isinstance(
                        child, dict
                    ):
                        return visit(option["kind"], child)
                return child

            if field["mapping"]:
                result[name] = {key: item(child) for key, child in result[name].items()}
            elif field["many"]:
                children = [item(child) for child in result[name]]
                if not field["ordered"]:
                    children.sort(key=lambda child: json.dumps(child, sort_keys=True))
                result[name] = children
            else:
                result[name] = item(result[name])
        return result

    return json.dumps(visit(kind, data), sort_keys=True, ensure_ascii=False)
