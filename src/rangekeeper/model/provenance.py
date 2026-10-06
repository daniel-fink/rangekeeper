"""Evidence lookup within a pinned Model, without loading external source content."""

from typing import TYPE_CHECKING
from uuid import UUID

from .._schema.records import (
    Provenance as Provenance,
    Source as Source,
    Claim as Claim,
    Fact as Fact,
    Location as Location,
    Method as Method,
    Reconciliation as Reconciliation,
)
from ..errors import MissingReferenceError, ReferenceTypeError
from ..validate import require_uuid

if TYPE_CHECKING:
    from .model import Model


def fact_for(model: "Model", target: UUID) -> Fact | None:
    """Return a target's recorded Fact, or None for a known declaration without one."""
    model.owner_of(target)  # Validate UUID existence without crossing revision scopes.
    return (
        next(
            (fact for fact in (model.provenance.facts or ()) if fact.target == target),
            None,
        )
        if model.provenance
        else None
    )


def locations(model: "Model", claim_id: UUID) -> tuple[Location, ...]:
    """Traverse upstream Claims once, preserving support order and unique Locations.

    Validated Models already prohibit cycles. Claim UUIDs are checked explicitly;
    no source file, URI or service is accessed. Repeated diamond support is deduplicated.
    """
    require_uuid(claim_id, "claim_id")
    model.claim(
        claim_id
    )  # Use the revision's existing typed index, not a new catalogue per Fact.
    seen, result = set(), []

    def visit(identity):
        if identity in seen:
            return
        seen.add(identity)
        for support in model.claim(identity).sources or ():
            if isinstance(support, UUID):
                visit(support)
            elif support not in result:
                result.append(support)

    visit(claim_id)
    return tuple(result)


__all__ = [
    "Provenance",
    "Source",
    "Claim",
    "Fact",
    "Location",
    "Method",
    "Reconciliation",
    "fact_for",
    "locations",
]
