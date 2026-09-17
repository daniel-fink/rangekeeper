"""Construct and inspect Evidence[Table] using stable row identities."""

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from ...provenance import Claim
from ...table import Row, Table
from ._profiles import _row_ids
from .errors import EvidenceValidationError
from .evidence import Evidence, EvidenceKey, Issue, _applicable


def from_claims(
    *,
    name: str,
    columns: Iterable[str],
    row_ids: Iterable[UUID],
    claims: Mapping[EvidenceKey, Claim[Any]],
    issues: Iterable[Issue] = (),
) -> Evidence[Table]:
    """Derive Table values from terminal Claims; reject missing/extra evidence."""
    # Delegate column and row identity normalization to Table, including its
    # existing errors, rather than maintaining a separate tabular schema.
    if isinstance(columns, (str, bytes)):
        raise TypeError("columns must be an iterable of strings")
    columns = Table(columns=tuple(columns), rows=()).columns
    row_ids = tuple(row_ids)
    skeleton = Table(
        columns=columns,
        rows=tuple(Row(values={c: None for c in columns}, id=uid) for uid in row_ids),
    )
    if not isinstance(claims, Mapping):
        raise TypeError("claims must be a mapping")
    rows = []
    for uid in _row_ids(skeleton):
        values = {}
        for column in columns:
            key = ("rows", str(uid), column)
            if key not in claims:
                raise EvidenceValidationError(
                    "claim_coverage", "Missing terminal Claim", key=key
                )
            claim_value = claims[key]
            if not isinstance(claim_value, Claim):
                raise TypeError("claims must contain Claim objects")
            values[column] = claim_value.value
        rows.append(Row(values=values, id=uid))
    return Evidence(
        name=name,
        data=Table(columns=columns, rows=tuple(rows)),
        claims=claims,
        issues=tuple(issues),
    )


def row(evidence: Evidence[Table], row_id: UUID) -> Row:
    """Resolve a row by UUID, never by display offset."""
    if not isinstance(evidence, Evidence) or not isinstance(evidence.data, Table):
        raise TypeError("Expected Evidence[Table]")
    if not isinstance(row_id, UUID):
        raise TypeError("row_id must be UUID")
    try:
        index = _row_ids(evidence.data).index(row_id)
    except ValueError as exc:
        raise KeyError(row_id) from exc
    return evidence.data.rows[index]


def claim(evidence: Evidence[Table], row_id: UUID, column: str) -> Claim[Any]:
    """Return the terminal Claim; traverse Claim.sources for its full lineage."""
    selected = row(evidence, row_id)
    if not isinstance(column, str):
        raise TypeError("column must be str")
    if column not in selected.values:
        raise KeyError(column)
    return evidence.claims[("rows", str(row_id), column)]


def issues_for(
    evidence: Evidence[Table],
    row_id: UUID,
    column: str | None = None,
) -> tuple[Issue, ...]:
    """Include ancestor scopes; row inspection also includes its cell issues."""
    row(evidence, row_id)
    if column is not None:
        claim(evidence, row_id, column)
    key = ("rows", str(row_id)) + (() if column is None else (column,))
    return tuple(
        issue
        for issue in evidence.issues
        if _applicable(issue, key)
        or (column is None and any(scope[:2] == key for scope in issue.at))
    )
