"""Typed catalogue lookup, separate from code searching."""

from uuid import UUID

from .._schema.records import (
    Definitions as Definitions,
    Measure,
    Taxonomy,
    Classification,
    Function,
)
from ..errors import MissingReferenceError, ReferenceTypeError
from ..validate import require_uuid, require_text


def _lookup(items, identity, kind):
    require_uuid(identity, "id")
    records = []
    if items:
        records.extend(items.measures or ())
        records.extend(items.functions or ())
        for taxonomy in items.taxonomies or ():
            records.append(taxonomy)
            records.extend(taxonomy.classifications)
    for record in records:
        if record.id == identity:
            if not isinstance(record, kind):
                raise ReferenceTypeError(
                    f"{identity} is {type(record).__name__}, expected {kind.__name__}"
                )
            return record
    raise MissingReferenceError(str(identity))


def measure(items: Definitions | None, id: UUID) -> Measure:
    """Resolve one Measure UUID; missing and wrong-kind catalogue entries differ."""
    return _lookup(items, id, Measure)


def taxonomy(items: Definitions | None, id: UUID) -> Taxonomy:
    """Resolve one Taxonomy UUID without guessing from its code."""
    return _lookup(items, id, Taxonomy)


def classification(items: Definitions | None, id: UUID) -> Classification:
    """Resolve a Classification across the declared Taxonomies by UUID."""
    return _lookup(items, id, Classification)


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


def find_taxonomies(items: Definitions | None, *, code: str) -> tuple[Taxonomy, ...]:
    """Search exact Taxonomy codes without interpreting them as identities."""
    require_text(code, "code")
    return (
        tuple(item for item in (items.taxonomies or ()) if item.code == code)
        if items
        else ()
    )


def find_classifications(
    items: Definitions | None, *, code: str
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


def find_functions(items: Definitions | None, *, code: str) -> tuple[Function, ...]:
    """Search declared Function codes; this does not resolve executable implementations."""
    require_text(code, "code")
    return (
        tuple(item for item in (items.functions or ()) if item.code == code)
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
    "function",
    "find_measures",
    "find_taxonomies",
    "find_classifications",
    "find_functions",
]
