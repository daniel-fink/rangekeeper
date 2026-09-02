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


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceEdition:
    id: UUID = field(default_factory=uuid4)
    name: str
    checksum: str
    issued_at: date | datetime | None = None
    received_at: date | datetime | None = None
    author: str | None = None

    def __post_init__(self) -> None:
        validate.require_uuid(self.id, "id")
        validate.require_text(self.name, "SourceEdition.name")
        validate.require_text(self.checksum, "SourceEdition.checksum")
        for value, field_name in (
            (self.issued_at, "issued_at"),
            (self.received_at, "received_at"),
        ):
            if value is not None and not isinstance(value, (date, datetime)):
                raise TypeError(f"{field_name} must be a date, datetime, or None")
        validate.optional_text(
            self.author,
            "SourceEdition.author",
            empty=False,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SpreadsheetLocation:
    edition: SourceEdition
    worksheet: str
    range: str

    def __post_init__(self) -> None:
        if not isinstance(self.edition, SourceEdition):
            raise TypeError("edition must be a SourceEdition")
        validate.require_text(self.worksheet, "SpreadsheetLocation.worksheet")
        validate.require_text(self.range, "SpreadsheetLocation.range")


class ClaimKind(Enum):
    SOURCED = "sourced"
    DERIVED = "derived"
    ASSERTED = "asserted"


@dataclass(frozen=True, slots=True, kw_only=True)
class Method:
    code: str
    version: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        validate.require_text(self.code, "Method.code")
        validate.optional_text(self.version, "Method.version", empty=False)
        validate.optional_text(self.description, "Method.description", empty=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class Claim(Generic[T]):
    id: UUID = field(default_factory=uuid4)
    value: T
    kind: ClaimKind
    sources: tuple[SpreadsheetLocation | Claim[Any], ...] = ()
    method: Method | None = None

    def __post_init__(self) -> None:
        validate.require_uuid(self.id, "id")
        if not isinstance(self.kind, ClaimKind):
            raise TypeError("kind must be a ClaimKind")
        sources = tuple(self.sources)
        if any(not isinstance(item, (SpreadsheetLocation, Claim)) for item in sources):
            raise TypeError("sources must contain SpreadsheetLocation or Claim objects")
        if self.method is not None and not isinstance(self.method, Method):
            raise TypeError("method must be a Method or None")
        if self.kind is ClaimKind.SOURCED and not any(
            isinstance(item, SpreadsheetLocation) for item in sources
        ):
            raise ValueError("a sourced claim requires a SpreadsheetLocation")
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
        at: SpreadsheetLocation,
        method: Method | None = None,
        id: UUID | None = None,
    ) -> Claim[T]:
        values = {
            "value": value,
            "kind": ClaimKind.SOURCED,
            "sources": (at,),
            "method": method,
        }
        if id is not None:
            values["id"] = id
        return cls(**values)

    @classmethod
    def derived(
        cls,
        value: T,
        *,
        from_claims: tuple[Claim[Any], ...],
        method: Method,
        id: UUID | None = None,
    ) -> Claim[T]:
        values = {
            "value": value,
            "kind": ClaimKind.DERIVED,
            "sources": tuple(from_claims),
            "method": method,
        }
        if id is not None:
            values["id"] = id
        return cls(**values)

    @classmethod
    def asserted(
        cls,
        value: T,
        *,
        method: Method,
        id: UUID | None = None,
    ) -> Claim[T]:
        values = {
            "value": value,
            "kind": ClaimKind.ASSERTED,
            "method": method,
        }
        if id is not None:
            values["id"] = id
        return cls(**values)


ClaimSource: TypeAlias = SpreadsheetLocation | Claim[Any]


@dataclass(frozen=True, slots=True)
class EntityState:
    code: str | None
    name: str | None
    classification: Classification | None

    @classmethod
    def from_entity(cls, entity: Entity) -> EntityState:
        if not isinstance(entity, Entity):
            raise TypeError("entity must be an Entity")
        return cls(
            code=entity.code,
            name=entity.name,
            classification=entity.classification,
        )


@dataclass(frozen=True, slots=True)
class AssemblyState(EntityState):
    entity_ids: frozenset[UUID]
    relationship_ids: frozenset[UUID]

    @classmethod
    def from_assembly(cls, assembly: Assembly) -> AssemblyState:
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
    source_id: UUID
    target_id: UUID
    classification: Classification

    @classmethod
    def from_relationship(cls, relationship: Relationship) -> RelationshipState:
        if not isinstance(relationship, Relationship):
            raise TypeError("relationship must be a Relationship")
        return cls(
            source_id=relationship.source_id,
            target_id=relationship.target_id,
            classification=relationship.classification,
        )


class ReconciliationStatus(Enum):
    PROVISIONAL = "provisional"
    CONFIRMED = "confirmed"


@dataclass(frozen=True, slots=True, kw_only=True)
class Reconciliation(Generic[T]):
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
    SINGLE_SOURCE = "single-source"
    MATCHED = "matched"
    CONFLICT = "conflict"
    PROVISIONAL = "provisional"
    RESOLVED = "resolved"


FactTarget: TypeAlias = Entity | Relationship | Label | Measurement | Feature


@dataclass(frozen=True, slots=True, kw_only=True)
class Fact(Generic[T]):
    target: FactTarget
    claims: tuple[Claim[T], ...]
    reconciliation: Reconciliation[T] | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.target, (Entity, Relationship, Label, Measurement, Feature)
        ):
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
        if self.reconciliation is not None:
            if self.reconciliation.status is ReconciliationStatus.PROVISIONAL:
                return FactStatus.PROVISIONAL
            return FactStatus.RESOLVED
        if len(self.claims) == 1:
            return FactStatus.SINGLE_SOURCE
        if _all_equivalent(tuple(claim.value for claim in self.claims)):
            return FactStatus.MATCHED
        return FactStatus.CONFLICT

    @property
    def current_claim(self) -> Claim[T] | None:
        if self.reconciliation is not None:
            return self.reconciliation.selected
        if len(self.claims) == 1 or _all_equivalent(
            tuple(claim.value for claim in self.claims)
        ):
            return self.claims[0]
        return None


def target_value(target: FactTarget) -> object:
    if isinstance(target, Measurement):
        return target.quantity
    if isinstance(target, Label):
        return target.classifications
    if isinstance(target, Feature):
        return target.value
    if isinstance(target, Assembly):
        return AssemblyState.from_assembly(target)
    if isinstance(target, Entity):
        return EntityState.from_entity(target)
    if isinstance(target, Relationship):
        return RelationshipState.from_relationship(target)
    raise TypeError("unsupported Fact target")


def values_equivalent(left: object, right: object) -> bool:
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


def _all_equivalent(values: tuple[object, ...]) -> bool:
    if not values:
        return True
    return all(values_equivalent(values[0], item) for item in values[1:])


def _index_claims(facts: Iterable[Fact[Any]]) -> Mapping[UUID, Claim[Any]]:
    claims_by_id: dict[UUID, Claim[Any]] = {}
    source_editions_by_id: dict[UUID, SourceEdition] = {}
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
            elif isinstance(source, SpreadsheetLocation):
                edition = source.edition
                registered_edition = source_editions_by_id.get(edition.id)
                if registered_edition is not None and registered_edition is not edition:
                    raise IdentityConflictError(
                        f"different SourceEditions share UUID {edition.id}"
                    )
                source_editions_by_id[edition.id] = edition
        visiting.remove(identity)
        visited.add(identity)

    for fact in facts:
        for claim in fact.claims:
            visit(claim)
    return MappingProxyType(claims_by_id)


def _index_graph_provenance(
    facts: Iterable[Fact[Any]],
    targets_by_id: Mapping[UUID, FactTarget],
) -> Mapping[UUID, Fact[Any]]:
    facts = tuple(facts)
    facts_by_target_id: dict[UUID, Fact[Any]] = {}
    for fact in facts:
        target_id = fact.target.id
        if target_id in facts_by_target_id:
            raise ValueError(f"more than one Fact targets UUID {target_id}")
        registered = targets_by_id.get(target_id)
        if registered is None:
            raise ValueError(
                f"Fact targets graph object {target_id} that is not present"
            )
        if registered is not fact.target:
            raise ValueError(
                f"Fact target {target_id} is not the registered Graph instance"
            )
        if fact.status is FactStatus.CONFLICT:
            raise ValueError(
                "conflicting claims require a provisional or confirmed reconciliation"
            )
        current_claim = fact.current_claim
        if current_claim is None or not values_equivalent(
            target_value(fact.target), current_claim.value
        ):
            raise ValueError(
                "the current Fact target value does not match its selected claim"
            )
        facts_by_target_id[target_id] = fact

    _index_claims(facts)
    return MappingProxyType(facts_by_target_id)
