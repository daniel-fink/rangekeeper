from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Generic, TypeAlias, TypeVar
from uuid import UUID, uuid4

import pint

from .. import validate
from .assembly import Assembly
from .characteristics import Feature, Label, Measurement
from .classification import Classification
from .entity import Entity
from .errors import IdentityConflictError
from .relationship import Relationship

T = TypeVar("T")

__all__ = [
    "AssemblyState",
    "Claim",
    "ClaimKind",
    "EntityState",
    "Fact",
    "FactStatus",
    "FactTarget",
    "Location",
    "Method",
    "Provenance",
    "Reconciliation",
    "ReconciliationStatus",
    "RelationshipState",
    "Source",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """An externally identifiable evidence artifact."""

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
    """A structured location within a Source."""

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
    """A sourced, derived, or asserted candidate value."""

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
        """Create a value tied to a location in an external source."""

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
        """Create a value derived from upstream claims by a named method."""

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
        """Create a value asserted directly by a named method."""

        return cls(
            id=uuid4() if id is None else id,
            value=value,
            kind=ClaimKind.ASSERTED,
            method=method,
        )


@dataclass(frozen=True, slots=True)
class EntityState:
    """The state compared when a Fact targets an entire Entity."""

    code: str | None
    name: str | None
    classification: Classification | None

    @classmethod
    def from_entity(cls, entity: Entity) -> EntityState:
        """Capture the fields represented by an entity-level Fact."""

        if not isinstance(entity, Entity):
            raise TypeError("entity must be an Entity")
        return cls(
            code=entity.code,
            name=entity.name,
            classification=entity.classification,
        )


@dataclass(frozen=True, slots=True)
class AssemblyState(EntityState):
    """Entity state plus the membership represented by an Assembly Fact."""

    entity_ids: frozenset[UUID]
    relationship_ids: frozenset[UUID]

    @classmethod
    def from_assembly(cls, assembly: Assembly) -> AssemblyState:
        """Capture every field represented by an assembly-level Fact."""

        if not isinstance(assembly, Assembly):
            raise TypeError("assembly must be an Assembly")
        return cls(
            code=assembly.code,
            name=assembly.name,
            classification=assembly.classification,
            entity_ids=assembly.entity_ids,
            relationship_ids=assembly.relationship_ids,
        )


@dataclass(frozen=True, slots=True)
class RelationshipState:
    """The endpoint and classification state represented by a Relationship Fact."""

    source_id: UUID
    target_id: UUID
    classification: Classification

    @classmethod
    def from_relationship(cls, relationship: Relationship) -> RelationshipState:
        """Capture the fields represented by a relationship-level Fact."""

        if not isinstance(relationship, Relationship):
            raise TypeError("relationship must be a Relationship")
        return cls(
            source_id=relationship.source_id,
            target_id=relationship.target_id,
            classification=relationship.classification,
        )


class ReconciliationStatus(Enum):
    """Whether a conflict resolution remains provisional or is confirmed."""

    PROVISIONAL = "provisional"
    CONFIRMED = "confirmed"


@dataclass(frozen=True, slots=True, kw_only=True)
class Reconciliation(Generic[T]):
    """The explicit selection of one Claim from a conflicting Fact."""

    selected: Claim[T]
    status: ReconciliationStatus
    method: Method | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.selected, Claim):
            raise TypeError("selected must be a Claim")
        if not isinstance(self.status, ReconciliationStatus):
            raise TypeError("status must be a ReconciliationStatus")
        if self.method is not None and not isinstance(self.method, Method):
            raise TypeError("method must be a Method or None")


class FactStatus(Enum):
    """The current agreement or reconciliation state of a Fact."""

    DETERMINATE = "determinate"
    CONFLICT = "conflict"
    RECONCILED = "reconciled"


FactTarget: TypeAlias = Entity | Relationship | Label | Measurement | Feature
_FACT_TARGET_TYPES = (Entity, Relationship, Label, Measurement, Feature)


@dataclass(frozen=True, slots=True, kw_only=True)
class Fact(Generic[T]):
    """Evidence binding one graph object or characteristic to candidate Claims."""

    target: FactTarget
    claims: tuple[Claim[T], ...]
    reconciliation: Reconciliation[T] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.target, _FACT_TARGET_TYPES):
            raise TypeError(
                "target must be an Entity, Relationship, Label, Measurement, or Feature"
            )
        claims = tuple(self.claims)
        if not claims:
            raise ValueError("a Fact requires at least one claim")
        if any(not isinstance(item, Claim) for item in claims):
            raise TypeError("claims must contain only Claim objects")
        if len({item.id for item in claims}) != len(claims):
            raise ValueError("a Fact cannot repeat a Claim UUID")
        if self.reconciliation is not None:
            if not isinstance(self.reconciliation, Reconciliation):
                raise TypeError("reconciliation must be a Reconciliation or None")
            if not any(item is self.reconciliation.selected for item in claims):
                raise ValueError(
                    "the selected reconciliation claim must belong to the Fact"
                )
        object.__setattr__(self, "claims", claims)

    @property
    def status(self) -> FactStatus:
        """Describe whether claims agree or required reconciliation."""

        if self.reconciliation is not None:
            return FactStatus.RECONCILED
        return (
            FactStatus.DETERMINATE
            if self.current_claim is not None
            else FactStatus.CONFLICT
        )

    @property
    def current_claim(self) -> Claim[T] | None:
        """Return the selected or agreed Claim, or None while values conflict."""

        if self.reconciliation is not None:
            return self.reconciliation.selected
        first, *others = self.claims
        if all(_values_equal(first.value, claim.value) for claim in others):
            return first
        return None


def _values_equal(left: object, right: object) -> bool:
    if isinstance(left, pint.Quantity) and isinstance(right, pint.Quantity):
        try:
            converted = right.to(left.units)
        except (pint.DimensionalityError, ValueError):
            return False
        comparison = left.magnitude == converted.magnitude
        try:
            return bool(comparison)
        except ValueError:
            return bool(comparison.all())
    try:
        comparison = left == right
        return bool(comparison)
    except (TypeError, ValueError):
        return False


def _index_evidence(
    facts: Iterable[Fact[Any]],
) -> tuple[Mapping[UUID, Claim[Any]], Mapping[UUID, Source]]:
    """Index Fact evidence through the shared Claim/Source identity validator."""
    return _index_claims(claim for fact in facts for claim in fact.claims)


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


def _validate_fact_values(facts: Iterable[Fact[Any]]) -> None:
    """Ensure each current Claim describes the state embedded in its target."""

    for fact in facts:
        current_claim = fact.current_claim
        if current_claim is None:
            raise ValueError(
                "conflicting claims require a provisional or confirmed reconciliation"
            )
        target = fact.target
        if isinstance(target, Measurement):
            target_value = target.quantity
        elif isinstance(target, Label):
            target_value = target.classifications
        elif isinstance(target, Feature):
            target_value = target.value
        elif isinstance(target, Assembly):
            target_value = AssemblyState.from_assembly(target)
        elif isinstance(target, Entity):
            target_value = EntityState.from_entity(target)
        elif isinstance(target, Relationship):
            target_value = RelationshipState.from_relationship(target)
        else:
            raise TypeError("unsupported Fact target")
        if not _values_equal(target_value, current_claim.value):
            raise ValueError(
                "the current Fact target value does not match its selected claim"
            )


@dataclass(frozen=True, slots=True)
class Provenance:
    """Immutable evidence explaining the current state of graph objects."""

    facts: tuple[Fact[Any], ...] = ()
    _facts_by_target_id: Mapping[UUID, Fact[Any]] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _claims_by_id: Mapping[UUID, Claim[Any]] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _sources_by_id: Mapping[UUID, Source] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        facts = tuple(self.facts)
        if any(not isinstance(fact, Fact) for fact in facts):
            raise TypeError("facts must contain only Fact objects")

        facts_by_target_id: dict[UUID, Fact[Any]] = {}
        for fact in facts:
            target_id = fact.target.id
            if target_id in facts_by_target_id:
                raise ValueError(f"more than one Fact targets UUID {target_id}")
            facts_by_target_id[target_id] = fact

        _validate_fact_values(facts)
        claims_by_id, sources_by_id = _index_evidence(facts)

        object.__setattr__(self, "facts", facts)
        object.__setattr__(
            self,
            "_facts_by_target_id",
            MappingProxyType(facts_by_target_id),
        )
        object.__setattr__(self, "_claims_by_id", claims_by_id)
        object.__setattr__(self, "_sources_by_id", sources_by_id)

    @property
    def claims(self) -> tuple[Claim[Any], ...]:
        """Return Claims in deterministic Fact and dependency discovery order."""

        return tuple(self._claims_by_id.values())

    @property
    def sources(self) -> tuple[Source, ...]:
        """Return Sources in first-discovered Claim dependency order."""

        return tuple(self._sources_by_id.values())

    def fact_for(self, target: UUID | FactTarget) -> Fact[Any] | None:
        """Return the sole Fact for a target UUID or canonical target instance."""

        if isinstance(target, UUID):
            target_id = target
        elif isinstance(target, _FACT_TARGET_TYPES):
            target_id = target.id
        else:
            raise TypeError("Fact lookup requires a graph object or UUID")

        fact = self._facts_by_target_id.get(target_id)
        if (
            fact is not None
            and not isinstance(target, UUID)
            and fact.target is not target
        ):
            raise IdentityConflictError(
                "the supplied Fact target is not the registered Provenance instance"
            )
        return fact
