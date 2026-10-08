"""Human-readable locations without losing format-independent source addresses."""

import json

from rangekeeper.workflow.evidence import locations

from rangekeeper.workflow._declarations import plain


def format_location(location) -> str:
    """Adapters may improve presentation; every other location has a lossless fallback."""
    from rangekeeper.workflow.catalog import REFERENCE_FORMATTERS

    for formatter in REFERENCE_FORMATTERS:
        rendered = formatter(location)
        if rendered is not None:
            return rendered
    address = json.dumps(plain(location.reference), ensure_ascii=False, sort_keys=True)
    return f"{location.source.name} · {address}"


def references(claims):
    return tuple(
        dict.fromkeys(format_location(loc) for c in claims for loc in locations(c))
    )
