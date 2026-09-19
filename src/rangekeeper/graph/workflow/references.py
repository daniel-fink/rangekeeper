"""Human-readable source references; structured lineage lives in provenance."""

from rangekeeper.graph.provenance import locations


def references(claims):
    return tuple(
        dict.fromkeys(
            f"{loc.source.name} · {loc.reference.get('sheet', '')}!{loc.reference.get('cell', '')}"
            for c in claims
            for loc in locations(c)
            if "cell" in loc.reference
        )
    )
