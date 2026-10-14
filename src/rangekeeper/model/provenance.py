"""Evidence lookup within a pinned Model, without loading external source content."""

from typing import TYPE_CHECKING
from uuid import UUID
from rangekeeper.schema.records import (
    Provenance as Provenance,
    Source as Source,
    Claim as Claim,
    Fact as Fact,
    Location as Location,
    Method as Method,
    Reconciliation as Reconciliation,
)
from rangekeeper.shared.errors import MissingReferenceError, ReferenceTypeError
from rangekeeper.shared.arguments import require_uuid
from rangekeeper.schema.enums import ClaimKind, ReconciliationStatus
from collections.abc import Mapping
from rangekeeper.shared.validation import require, require_acyclic


if TYPE_CHECKING:
    from rangekeeper.model.model import Model


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


__all__ += ["ClaimKind", "ReconciliationStatus"]


def check_provenance(provenance, *, scope, targets, paths):
    """Check captured evidence relationships without evaluating Claim content."""
    from rangekeeper.model.scenario.contracts import validate_realizations

    validate_realizations(provenance, scope)

    sources = {r["id"]: r for r in provenance.get("sources") or []}
    claims = {r["id"]: r for r in provenance.get("claims") or []}
    for value in scope.values.values():
        for movement in (value.get("flow") or {}).get("movements") or []:
            require(
                all(identity in claims for identity in movement.get("claims") or []),
                "unknown movement Claim",
                path=paths[movement["id"]] + "/claims",
            )
    parents = {}
    for claim in claims.values():
        path = paths[claim["id"]]
        support = claim.get("sources") or []
        locations = [s for s in support if isinstance(s, Mapping)]
        upstream = [s for s in support if isinstance(s, str)]
        require(
            all(s["source"] in sources for s in locations),
            "unknown Source",
            path=path + "/sources",
        )
        require(
            all(c in claims for c in upstream),
            "unknown upstream Claim",
            path=path + "/sources",
        )
        if claim["kind"] == "sourced":
            require(
                bool(locations),
                "sourced Claim needs a Location",
                path=path + "/sources",
            )
        if claim["kind"] == "derived":
            require(
                bool(upstream),
                "derived Claim needs an upstream Claim",
                path=path + "/sources",
            )
        parents[claim["id"]] = upstream
    require_acyclic(parents, "Claim dependency", path="/provenance/claims")
    fact_targets = set()
    for index, fact in enumerate(provenance.get("facts") or []):
        path = f"/provenance/facts/{index}"
        target = fact["target"]
        require(
            target in targets,
            "unknown or ineligible Fact target",
            path=path + "/target",
        )
        require(
            target not in fact_targets, "duplicate Fact target", path=path + "/target"
        )
        fact_targets.add(target)
        support = fact["claims"]
        require(bool(support), "Fact needs a Claim", path=path + "/claims")
        require(
            len(support) == len(set(support)),
            "duplicate Fact Claim",
            path=path + "/claims",
        )
        require(
            all(c in claims for c in support),
            "unknown supporting Claim",
            path=path + "/claims",
        )
        reconciliation = fact.get("reconciliation")
        if reconciliation:
            require(
                reconciliation["selected"] in support,
                "selected Claim outside Fact",
                path=path + "/reconciliation/selected",
            )
