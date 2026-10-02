"""Representation comparison guided by generated ordering annotations.

Only schema-declared unordered collections are sorted. Opaque content, ordered
mathematics and null/omitted/empty distinctions retain their supplied meaning.
"""

import json

from ._records import _json_copy
from ._schema.validation import slots_for


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
