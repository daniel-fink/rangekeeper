"""Versioned deterministic encoding of complete Evidence artifacts."""

from typing import Any

from ...provenance import Location
from ...table import Table
from ._encoding import digest, encode
from .errors import EvidenceValidationError
from .evidence import Evidence
from .validation import _validated_indexes


def _encode_content(data: object) -> object:
    if type(data) is not Table:
        raise EvidenceValidationError(
            "unsupported_content", f"Unsupported content type {type(data).__name__}"
        )
    return {
        "columns": data.columns,
        "rows": [
            [str(row.id), [encode(row.values[c]) for c in data.columns]]
            for row in data.rows
        ],
    }


def fingerprint(evidence: Evidence[Any]) -> str:
    """Return a versioned SHA-256 content digest, not a persistence encoding.

    Inputs must use stable explicit identities for repeatable independent builds.
    Display names/messages are content and included; runtime/job metadata is not
    represented here. Source/rule versions travel through their existing Claims.
    """
    claims, sources = _validated_indexes(evidence)
    source_rows = [
        [
            str(s.id),
            s.name,
            s.checksum,
            encode(s.issued_at),
            encode(s.received_at),
            s.author,
        ]
        for s in sorted(sources.values(), key=lambda s: str(s.id))
    ]
    claim_rows = []
    for claim in sorted(claims.values(), key=lambda c: str(c.id)):
        inputs = [
            ["location", str(x.source.id), sorted(x.reference.items())]
            if isinstance(x, Location)
            else ["claim", str(x.id)]
            for x in claim.sources
        ]
        method = (
            None
            if claim.method is None
            else [claim.method.code, claim.method.version, claim.method.description]
        )
        claim_rows.append([
            str(claim.id),
            claim.kind.value,
            encode(claim.value),
            inputs,
            method,
        ])
    issues = [
        [
            issue.id,
            issue.rule_id,
            issue.code,
            issue.severity.value,
            issue.message,
            sorted(issue.at),
            sorted(str(c.id) for c in issue.related_claims),
            [[k, encode(v)] for k, v in sorted(issue.details.items())],
        ]
        for issue in sorted(evidence.issues, key=lambda i: i.id)
    ]
    return "sha256:" + digest({
        "format": "rk.evidence/v1",
        "profile": "rk.table-evidence/v1",
        "name": evidence.name,
        "data": _encode_content(evidence.data),
        "outputs": [
            [key, str(claim.id)] for key, claim in sorted(evidence.claims.items())
        ],
        "sources": source_rows,
        "claims": claim_rows,
        "issues": issues,
    })
