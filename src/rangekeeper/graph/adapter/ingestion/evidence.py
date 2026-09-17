"""Immutable operation outputs tied to existing RK Claims and Locations."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from ...provenance import Claim
from ._encoding import digest, encode
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
        from .validation import validate

        validate(self)


def _applicable(issue: Issue, key: EvidenceKey) -> bool:
    return any(key[: len(scope)] == scope for scope in issue.at)
