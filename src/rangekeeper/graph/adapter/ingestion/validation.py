"""Structural validation of associations between content, Claims and issues."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from ...provenance import Claim, Source, _index_claims
from ...table import Table
from ._encoding import encode
from .errors import EvidenceValidationError
from .evidence import Evidence, Issue, _applicable
from .tabular import _cell, _cell_keys, _validate_scope, _validate_table


def _validated_indexes(
    evidence: Evidence[Any],
) -> tuple[Mapping[UUID, Claim[Any]], Mapping[UUID, Source]]:
    if not isinstance(evidence, Evidence):
        raise TypeError("Expected Evidence")
    if type(evidence.data) is not Table:
        raise EvidenceValidationError(
            "unsupported_content",
            f"Unsupported content type {type(evidence.data).__name__}",
        )
    _validate_table(evidence.data)
    if any(not isinstance(issue, Issue) for issue in evidence.issues):
        raise TypeError("issues must contain Issue objects")
    if len({issue.id for issue in evidence.issues}) != len(evidence.issues):
        raise EvidenceValidationError("duplicate_issue", "Duplicate Issue IDs")
    required = _cell_keys(evidence.data)
    if set(required) != set(evidence.claims):
        raise EvidenceValidationError(
            "claim_coverage", "Claims must match declared outputs exactly"
        )
    for issue in evidence.issues:
        for scope in issue.at:
            _validate_scope(evidence.data, scope)
    roots = (
        *evidence.claims.values(),
        *(c for issue in evidence.issues for c in issue.related_claims),
    )
    # Share graph provenance's canonical-instance and cycle validation. Do not
    # invent Facts for pre-graph claims or weaken identity rules.
    claims, sources = _index_claims(roots)
    for claim in claims.values():
        encode(claim.value)
    for source in sources.values():
        encode(source.issued_at)
        encode(source.received_at)
    for key, claim in evidence.claims.items():
        value = _cell(evidence.data, key)
        if encode(value) != encode(claim.value):
            raise EvidenceValidationError(
                "value_mismatch", "Output differs from terminal Claim", key=key
            )
        if value is None and not any(
            _applicable(issue, key) for issue in evidence.issues
        ):
            raise EvidenceValidationError(
                "unexplained_missing",
                "None requires an applicable explanatory issue",
                key=key,
            )
    return claims, sources


def validate(evidence: Evidence[Any]) -> None:
    """Validate shape, immutable values, addressing and evidence associations.

    Does not infer usability or execute an operation's missing-value policy.
    """
    _validated_indexes(evidence)
