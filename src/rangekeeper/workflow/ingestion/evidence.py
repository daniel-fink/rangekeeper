"""Immutable operation outputs tied to existing RK Claims and Locations."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from rangekeeper.operation import IssueSeverity
from rangekeeper.evidence import Claim
from rangekeeper.workflow.ingestion._encoding import digest, encode
from rangekeeper.workflow.ingestion.errors import EvidenceValidationError

# Stable address segments let Issue scopes survive row reordering and selection.
EvidenceKey = tuple[str, ...]
T = TypeVar("T")


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

    Keeps a limitation visible where it applies, including on otherwise usable
    output. Consumers must not treat a warning as permission to replace missing
    data with zero.
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
            + digest(
                [
                    "rk.issue/v1",
                    self.rule_id,
                    self.code,
                    sorted(scopes),
                    sorted(str(claim.id) for claim in related),
                ]
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence(Generic[T]):
    """A supported snapshot with one terminal Claim per declared output.

    Keeps table values, their terminal Claims and explanations together so
    transformations cannot silently detach values from support. Row UUIDs
    preserve addressing through selection and reordering; validation currently
    supports Table content only.
    """

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
        from rangekeeper.workflow.ingestion.validation import validate

        validate(self)


def _applicable(issue: Issue, key: EvidenceKey) -> bool:
    return any(key[: len(scope)] == scope for scope in issue.at)
