"""Immutable operation outputs tied to existing RK Claims and Locations."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from ...provenance import Claim, Location, _index_claims
from ._profiles import profile_for
from ._values import digest, encode
from .errors import EvidenceValidationError

EvidenceKey = tuple[str, ...]
T = TypeVar("T")


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


def _key(value: object) -> EvidenceKey:
    if not isinstance(value, (tuple, list)) or any(
        type(segment) is not str or not segment for segment in value
    ):
        raise EvidenceValidationError(
            "invalid_address", "Address must contain nonempty string segments"
        )
    return tuple(value)


def _text(value: object, field_name: str) -> None:
    if type(value) is not str or not value.strip():
        raise EvidenceValidationError(
            "invalid_field", f"{field_name} must be nonempty text"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Issue:
    """What happened to evidence; consuming rules decide execution consequences.

    Severity is presentational. No severity or code automatically blocks an
    operation or selects a value. Identity excludes prose, severity and details.
    """

    rule_id: str
    code: str
    severity: IssueSeverity
    message: str
    at: tuple[EvidenceKey, ...]
    related_claims: tuple[Claim[Any], ...] = ()
    details: Mapping[str, object] = field(default_factory=dict)
    id: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("rule_id", "code", "message"):
            _text(getattr(self, name), name)
        if not isinstance(self.severity, IssueSeverity):
            raise TypeError("severity must be IssueSeverity")
        scopes = tuple(_key(key) for key in self.at)
        if not scopes or len(set(scopes)) != len(scopes):
            raise EvidenceValidationError(
                "invalid_scope", "Issue scopes must be nonempty and unique"
            )
        related = tuple(self.related_claims)
        if any(not isinstance(claim, Claim) for claim in related):
            raise TypeError("related_claims must contain Claim objects")
        if len({claim.id for claim in related}) != len(related):
            raise EvidenceValidationError(
                "duplicate_claim", "Duplicate related Claim IDs"
            )
        if not isinstance(self.details, Mapping):
            raise TypeError("details must be a mapping")
        details = dict(self.details)
        for key, value in details.items():
            _text(key, "details key")
            encode(value)
        object.__setattr__(self, "at", scopes)
        object.__setattr__(self, "related_claims", related)
        object.__setattr__(self, "details", MappingProxyType(details))
        object.__setattr__(
            self,
            "id",
            "I-"
            + digest([
                "rk.issue/v1",
                self.rule_id,
                self.code,
                sorted(scopes),
                sorted(str(claim.id) for claim in related),
            ]),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence(Generic[T]):
    """A supported snapshot with one terminal Claim per declared output."""

    name: str
    data: T
    claims: Mapping[EvidenceKey, Claim[Any]]
    issues: tuple[Issue, ...] = ()

    def __post_init__(self) -> None:
        _text(self.name, "name")
        if not isinstance(self.claims, Mapping):
            raise TypeError("claims must be a mapping")
        claims = {_key(key): value for key, value in self.claims.items()}
        object.__setattr__(self, "claims", MappingProxyType(claims))
        object.__setattr__(self, "issues", tuple(self.issues))
        validate(self)


def _applicable(issue: Issue, key: EvidenceKey) -> bool:
    return any(key[: len(scope)] == scope for scope in issue.at)


def _validate(evidence: Evidence[Any]):
    if not isinstance(evidence, Evidence):
        raise TypeError("Expected Evidence")
    profile = profile_for(evidence.data)
    profile.validate_data(evidence.data)
    if any(not isinstance(issue, Issue) for issue in evidence.issues):
        raise TypeError("issues must contain Issue objects")
    if len({issue.id for issue in evidence.issues}) != len(evidence.issues):
        raise EvidenceValidationError("duplicate_issue", "Duplicate Issue IDs")
    required = profile.required_outputs(evidence.data)
    if required is not None and set(required) != set(evidence.claims):
        raise EvidenceValidationError(
            "claim_coverage", "Claims must match declared outputs exactly"
        )
    for issue in evidence.issues:
        for scope in issue.at:
            profile.validate_scope(evidence.data, scope)
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
        value = profile.resolve_output(evidence.data, key)
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
    return profile, claims, sources


def validate(evidence: Evidence[Any]) -> None:
    """Validate shape, immutable values, addressing and evidence associations.

    Does not infer usability or execute an operation's missing-value policy.
    """
    _validate(evidence)


def fingerprint(evidence: Evidence[Any]) -> str:
    """Return a versioned SHA-256 content digest, not a persistence encoding.

    Inputs must use stable explicit identities for repeatable independent builds.
    Display names/messages are content and included; runtime/job metadata is not
    represented here. Source/rule versions travel through their existing Claims.
    """
    profile, claims, sources = _validate(evidence)
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
        "profile": profile.format,
        "name": evidence.name,
        "data": profile.encode_data(evidence.data),
        "outputs": [
            [key, str(claim.id)] for key, claim in sorted(evidence.claims.items())
        ],
        "sources": source_rows,
        "claims": claim_rows,
        "issues": issues,
    })
