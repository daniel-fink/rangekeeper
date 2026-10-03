"""Transient source observations and support chains used by readers and workflows.

These objects may hold native source values. They are converted explicitly into
schema Claims when a workflow publishes its in-memory Model; they are not Model
records or a persistence format.
"""

from __future__ import annotations
from collections.abc import Mapping, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4
from . import validate
from .errors import IdentityConflictError

T = TypeVar("T")


@dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """An externally identifiable evidence artifact.

    Identifies the edition an observation came from so later interpretations can
    be audited against the same evidence.
    """

    id: UUID = field(default_factory=uuid4)
    name: str
    checksum: str
    issued_at: date | datetime | None = None
    received_at: date | datetime | None = None
    author: str | None = None

    def __post_init__(self) -> None:
        validate.require_uuid(self.id, "id")
        validate.require_text(self.name, "Source.name")
        validate.require_text(self.checksum, "Source.checksum")
        for value, field_name in (
            (self.issued_at, "issued_at"),
            (self.received_at, "received_at"),
        ):
            if value is not None and not isinstance(value, (date, datetime)):
                raise TypeError(f"{field_name} must be a date, datetime, or None")
        validate.optional_text(
            self.author,
            "Source.author",
            empty=False,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Location:
    """A structured location within a Source.

    Keeps a source address separate from its displayed value, allowing a Claim
    to remain traceable after extraction or reordering.
    """

    source: Source
    reference: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            raise TypeError("source must be a Source")
        if not isinstance(self.reference, Mapping):
            raise TypeError("reference must be a mapping")
        reference = dict(self.reference)
        for key, value in reference.items():
            validate.require_text(key, "Location.reference key")
            validate.require_text(value, f"Location.reference[{key!r}]")
        object.__setattr__(self, "reference", MappingProxyType(reference))


class ClaimKind(Enum):
    """How a Claim's value entered the evidence graph."""

    SOURCED = "sourced"
    DERIVED = "derived"
    ASSERTED = "asserted"


@dataclass(frozen=True, slots=True, kw_only=True)
class Method:
    """The named process used to assert, derive, or reconcile evidence."""

    code: str
    version: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        validate.require_text(self.code, "Method.code")
        validate.optional_text(self.version, "Method.version", empty=False)
        validate.optional_text(self.description, "Method.description", empty=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class Claim(Generic[T]):
    """A sourced, derived, or asserted candidate value.

    Retains a candidate value and its support before any decision about the
    accepted graph state. Derived Claims preserve their inputs instead of
    overwriting observations.
    """

    id: UUID = field(default_factory=uuid4)
    value: T
    kind: ClaimKind
    sources: tuple[Location | Claim[Any], ...] = ()
    method: Method | None = None

    def __post_init__(self) -> None:
        validate.require_uuid(self.id, "id")
        if not isinstance(self.kind, ClaimKind):
            raise TypeError("kind must be a ClaimKind")
        sources = tuple(self.sources)
        if any(not isinstance(item, (Location, Claim)) for item in sources):
            raise TypeError("sources must contain Location or Claim objects")
        if self.method is not None and not isinstance(self.method, Method):
            raise TypeError("method must be a Method or None")
        if self.kind is ClaimKind.SOURCED and not any(
            isinstance(item, Location) for item in sources
        ):
            raise ValueError("a sourced claim requires a Location")
        if self.kind is ClaimKind.DERIVED:
            if not any(isinstance(item, Claim) for item in sources):
                raise ValueError("a derived claim requires an upstream Claim")
            if self.method is None:
                raise ValueError("a derived claim requires a method")
        if self.kind is ClaimKind.ASSERTED and self.method is None:
            raise ValueError("an asserted claim requires a method")
        object.__setattr__(self, "sources", sources)

    @classmethod
    def sourced(
        cls,
        value: T,
        *,
        at: Location,
        method: Method | None = None,
        id: UUID | None = None,
    ) -> Claim[T]:
        """Create a value tied to a location in an external source.

        Use this for an observation whose authority is an address in a source;
        subsequent interpretation should derive another Claim.
        """

        return cls(
            id=uuid4() if id is None else id,
            value=value,
            kind=ClaimKind.SOURCED,
            sources=(at,),
            method=method,
        )

    @classmethod
    def derived(
        cls,
        value: T,
        *,
        from_claims: tuple[Claim[Any], ...],
        method: Method,
        id: UUID | None = None,
    ) -> Claim[T]:
        """Create a value derived from upstream claims by a named method.

        Use this when a value depends on prior Claims so an explanation can
        follow the calculation or interpretation back to its inputs.
        """

        return cls(
            id=uuid4() if id is None else id,
            value=value,
            kind=ClaimKind.DERIVED,
            sources=tuple(from_claims),
            method=method,
        )

    @classmethod
    def asserted(
        cls,
        value: T,
        *,
        method: Method,
        id: UUID | None = None,
    ) -> Claim[T]:
        """Create a value asserted directly by a named method.

        Use this for a declared assertion with a named method, keeping it
        distinguishable from a direct source observation or derivation.
        """

        return cls(
            id=uuid4() if id is None else id,
            value=value,
            kind=ClaimKind.ASSERTED,
            method=method,
        )


def locations(claim: Claim) -> tuple[Location, ...]:
    """Return source locations once per lineage, independent of source format.

    Shared ancestors are visited once so graph checks and adapters can inspect
    provenance without depending on a reader or presentation implementation.
    """
    result = {}
    visited = set()

    def visit(item):
        if item.id in visited:
            return
        visited.add(item.id)
        for source in item.sources:
            if isinstance(source, Location):
                key = (source.source.id, tuple(sorted(source.reference.items())))
                result.setdefault(key, source)
            else:
                visit(source)

    visit(claim)
    return tuple(result.values())


def _index_claims(
    roots: Iterable[Claim[Any]],
) -> tuple[Mapping[UUID, Claim[Any]], Mapping[UUID, Source]]:
    """Index roots without requiring graph targets; preserve canonical identity."""

    claims_by_id: dict[UUID, Claim[Any]] = {}
    sources_by_id: dict[UUID, Source] = {}
    visited: set[int] = set()
    visiting: set[int] = set()

    def visit(claim: Claim[Any]) -> None:
        identity = id(claim)
        if identity in visiting:
            raise ValueError("claim dependency graph must be acyclic")
        registered = claims_by_id.get(claim.id)
        if registered is not None and registered is not claim:
            raise IdentityConflictError(f"different Claims share UUID {claim.id}")
        claims_by_id[claim.id] = claim
        if identity in visited:
            return
        visiting.add(identity)
        for source in claim.sources:
            if isinstance(source, Claim):
                visit(source)
            elif isinstance(source, Location):
                registered_source = sources_by_id.get(source.source.id)
                if (
                    registered_source is not None
                    and registered_source is not source.source
                ):
                    raise IdentityConflictError(
                        f"different Sources share UUID {source.source.id}"
                    )
                sources_by_id[source.source.id] = source.source
        visiting.remove(identity)
        visited.add(identity)

    for claim in roots:
        if not isinstance(claim, Claim):
            raise TypeError("roots must contain Claim objects")
        visit(claim)
    return MappingProxyType(claims_by_id), MappingProxyType(sources_by_id)


__all__ = ["Source", "Location", "ClaimKind", "Method", "Claim", "locations"]
