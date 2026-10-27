"""Typed catalogue lookup, separate from code searching."""

from uuid import UUID

from rangekeeper.schema.records import (
    Classification,
    Function,
    Measure,
    Taxonomy,
)
from rangekeeper.schema.records import (
    Definitions as Definitions,
)
from rangekeeper.shared.arguments import require_text, require_uuid
from rangekeeper.shared.validation import require, require_acyclic, require_unique


def _lookup(items, identity, kind):
    require_uuid(identity, "id")
    from rangekeeper.schema.index import RecordIndex

    return RecordIndex.build(items or Definitions()).get(identity, kind)


def measure(items: Definitions | None, id: UUID) -> Measure:
    """Resolve one Measure UUID; missing and wrong-kind catalogue entries differ."""
    return _lookup(items, id, Measure)


def taxonomy(items: Definitions | None, id: UUID) -> Taxonomy:
    """Resolve one Taxonomy UUID without guessing from its code."""
    return _lookup(items, id, Taxonomy)


def classification(items: Definitions | None, id: UUID) -> Classification:
    """Resolve a Classification across the declared Taxonomies by UUID."""
    return _lookup(items, id, Classification)


def descendants(items: Definitions | None, id: UUID) -> tuple[Classification, ...]:
    """Return a Classification's sub-types in its Taxonomy, in declaration order.

    The result follows each Classification's ``parent`` to any depth and excludes
    the Classification itself. A leaf Classification has no descendants. A missing
    or wrong-kind UUID raises, as for ``classification``.
    """
    classification(items, id)
    return _descendants(items, id)


def _descendants(items, id):
    # The caller has resolved the UUID. Each Classification UUID is unique in the catalogue.
    for record in items.taxonomies or ():
        records = record.classifications
        if not any(item.id == id for item in records):
            continue
        children: dict[UUID, list[UUID]] = {}
        for item in records:
            if item.parent is not None:
                children.setdefault(item.parent, []).append(item.id)
        found, pending = set(), [id]
        while pending:
            for child in children.get(pending.pop(), ()):
                if child not in found:
                    found.add(child)
                    pending.append(child)
        return tuple(item for item in records if item.id in found)
    return ()


def _classes(items, id, *, exclusive):
    """UUIDs that match a classification selector, with sub-types unless exclusive."""
    if type(exclusive) is not bool:
        raise TypeError("exclusive must be bool")
    classification(items, id)
    if exclusive:
        return frozenset((id,))
    return frozenset((id, *(item.id for item in _descendants(items, id))))


def function(items: Definitions | None, id: UUID) -> Function:
    """Resolve a declared Function signature, not an executable callback."""
    return _lookup(items, id, Function)


def find_measures(items: Definitions | None, *, code: str) -> tuple[Measure, ...]:
    """Search exact case-sensitive codes in declaration order; no match is empty."""
    require_text(code, "code")
    return (
        tuple(item for item in (items.measures or ()) if item.code == code)
        if items
        else ()
    )


def find_classifications(
    items: Definitions | None,
    *,
    code: str,
) -> tuple[Classification, ...]:
    """Search across Taxonomies; the same local code can yield several matches."""
    require_text(code, "code")
    return (
        tuple(
            item
            for taxonomy in (items.taxonomies or ())
            for item in taxonomy.classifications
            if item.code == code
        )
        if items
        else ()
    )


__all__ = [
    "Definitions",
    "Taxonomy",
    "Classification",
    "Function",
    "Measure",
    "measure",
    "taxonomy",
    "classification",
    "descendants",
    "function",
    "find_measures",
    "find_classifications",
]


def check_definitions(definitions):
    """Check catalogue names and Taxonomy-local ancestry."""
    for collection in ("taxonomies", "measures", "functions"):
        require_unique(
            definitions.get(collection) or [],
            "code",
            "Function code" if collection == "functions" else f"{collection} code",
            path=f"/definitions/{collection}",
        )
    for taxonomy_index, taxonomy in enumerate(definitions.get("taxonomies") or []):
        records = taxonomy["classifications"]
        path = f"/definitions/taxonomies/{taxonomy_index}/classifications"
        require(bool(records), "empty Taxonomy", path=path)
        require_unique(
            records,
            "code",
            "Classification code",
            path=f"/definitions/taxonomies/{taxonomy_index}/classifications",
        )
        local = {r["id"] for r in records}
        parents = {}
        roots = []
        for index, record in enumerate(records):
            parent = record.get("parent")
            if parent is None:
                roots.append(record)
            else:
                require(
                    parent in local,
                    "Classification parent outside Taxonomy",
                    path=f"{path}/{index}/parent",
                )
                parents[record["id"]] = [parent]
        require_acyclic(parents, "Classification parent", path=path)
        require(len(roots) == 1, "Taxonomy must have one root", path=path)
