"""Structural validation of associations between content, Claims and issues."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from uuid import UUID

from rangekeeper.evidence import Claim, Source, _index_claims
from rangekeeper.table import Table, Row
from rangekeeper.evidence.errors import encode
from rangekeeper.evidence.errors import EvidenceValidationError
from rangekeeper.evidence.evidence import Evidence, EvidenceKey, Issue


def _validate_table(table: Table) -> None:
    if any(row.id is None for row in table.rows):
        raise EvidenceValidationError(
            "missing_row_ids", "Evidence requires an ID on every row"
        )
    for item in table.rows:
        for value in item.values.values():
            encode(value)


def _addressed_row(table: Table, key: EvidenceKey) -> Row:
    try:
        identifier = UUID(key[1])
        if str(identifier) != key[1]:
            raise ValueError("Noncanonical UUID")
        return table.row(identifier)
    except (ValueError, IndexError, KeyError) as exc:
        raise EvidenceValidationError(
            "invalid_address", "Unknown/noncanonical row ID", key=key
        ) from exc


def _validate_scope(table: Table, key: EvidenceKey) -> None:
    if not key:
        return
    if len(key) not in (2, 3) or key[0] != "rows":
        raise EvidenceValidationError(
            "invalid_address", "Expected row or cell address", key=key
        )
    _addressed_row(table, key)
    if len(key) == 3 and key[2] not in table.columns:
        raise EvidenceValidationError("invalid_address", "Unknown column", key=key)


def _cell(table: Table, key: EvidenceKey) -> object:
    _validate_scope(table, key)
    if len(key) != 3:
        raise EvidenceValidationError(
            "invalid_address", "Claim must address a cell", key=key
        )
    return _addressed_row(table, key).values[key[2]]


def _cell_keys(table: Table) -> Iterable[EvidenceKey]:
    return (
        ("rows", str(uid), column)
        for uid in (row.id for row in table.rows)
        for column in table.columns
    )


def _validated_indexes(
    evidence: Evidence[Any],
) -> tuple[Mapping[UUID, Claim[Any]], Mapping[UUID, Source], Mapping]:
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
    scopes = _index_issues(evidence.issues)
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
        if value is None and not _issues_for(scopes, (key,)):
            raise EvidenceValidationError(
                "unexplained_missing",
                "None requires an applicable explanatory issue",
                key=key,
            )
    return claims, sources, scopes


def validate(evidence: Evidence[Any]) -> None:
    """Validate shape, immutable values, addressing and evidence associations.

    Does not infer usability or execute an operation's missing-value policy.

    Establishes that an Evidence artifact is internally trustworthy before
    another operation consumes it. Construction already invokes this check; it
    does not establish business correctness.
    """
    _validated_indexes(evidence)


@dataclass(frozen=True, slots=True)
class PreparedEvidence:
    """Validated indexes and identity for one exact Evidence input and operation."""

    evidence: Evidence
    claims: Mapping
    sources: Mapping
    issues: Mapping
    fingerprint: str

    def issues_for(self, key):
        return _issues_for(self.issues, (key,))


def _index_issues(issues, *, scopes=None, start=0):
    """Append scope entries with their original global ordering positions."""
    scopes = {} if scopes is None else scopes
    for position, issue in enumerate(issues, start):
        for scope in issue.at:
            scopes.setdefault(scope, []).append((position, issue))
    return scopes


def _issues_for(scopes, keys):
    applicable = {
        position: issue
        for key in keys
        for n in range(len(key) + 1)
        for position, issue in scopes.get(key[:n], ())
    }
    return tuple(applicable[position] for position in sorted(applicable))


def prepare(evidence: Evidence) -> PreparedEvidence:
    from .fingerprint import _fingerprint

    claims, sources, scopes = _validated_indexes(evidence)
    return PreparedEvidence(
        evidence,
        claims,
        sources,
        MappingProxyType({key: tuple(value) for key, value in scopes.items()}),
        _fingerprint(evidence, claims, sources),
    )
