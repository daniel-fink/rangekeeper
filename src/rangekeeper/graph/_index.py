from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from .errors import (
    AmbiguousDefinitionError,
    IdentityConflictError,
    NonCanonicalDefinitionError,
    UnknownDefinitionError,
)


class Identified(Protocol):
    id: UUID


class CodedIdentified(Identified, Protocol):
    code: str


T = TypeVar("T", bound=Identified)
C = TypeVar("C", bound=CodedIdentified)
K = TypeVar("K", bound=Hashable)


@dataclass(frozen=True, slots=True)
class Catalog(Generic[C]):
    """Immutable UUID and code indexes for one definition kind."""

    items: tuple[C, ...]
    kind: str
    unique_codes: bool = field(default=True, repr=False)
    scope: str | None = field(default=None, repr=False)
    _by_id: Mapping[UUID, C] = field(init=False, repr=False, compare=False)
    _by_code: Mapping[str, tuple[UUID, ...]] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        items = tuple(self.items)
        by_id = index_by_id(items, self.kind)
        by_code = multi_index(items, lambda item: item.code)
        if self.unique_codes:
            for code, identifiers in by_code.items():
                if len(identifiers) > 1:
                    raise ValueError(f"{self.kind} codes must be unique: {code!r}")
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "_by_id", by_id)
        object.__setattr__(self, "_by_code", by_code)

    def by_id(self, identifier: UUID) -> C:
        if not isinstance(identifier, UUID):
            raise TypeError(f"{self.kind} id must be a UUID")
        try:
            return self._by_id[identifier]
        except KeyError as error:
            raise UnknownDefinitionError(
                self.kind, identifier, scope=self.scope
            ) from error

    def by_code(self, code: str) -> C:
        if not isinstance(code, str):
            raise TypeError(f"{self.kind} code must be a string")
        identifiers = self._by_code.get(code, ())
        if not identifiers:
            raise UnknownDefinitionError(self.kind, code, scope=self.scope)
        if len(identifiers) > 1:
            raise AmbiguousDefinitionError(
                self.kind, code, len(identifiers), scope=self.scope
            )
        return self._by_id[identifiers[0]]

    def find(self, code: str) -> C | None:
        if not isinstance(code, str):
            raise TypeError(f"{self.kind} code must be a string")
        identifiers = self._by_code.get(code, ())
        if not identifiers:
            return None
        if len(identifiers) > 1:
            raise AmbiguousDefinitionError(
                self.kind, code, len(identifiers), scope=self.scope
            )
        return self._by_id[identifiers[0]]

    def canonical(self, value: C) -> C:
        canonical = self._by_id.get(value.id)
        if canonical is None:
            raise UnknownDefinitionError(self.kind, value.id, scope=self.scope)
        if canonical is not value:
            raise NonCanonicalDefinitionError(self.kind, value.id, scope=self.scope)
        return canonical

    def contains_id(self, identifier: UUID) -> bool:
        return identifier in self._by_id


def index_by_id(items: Iterable[T], kind: str) -> Mapping[UUID, T]:
    """Build an immutable, insertion-ordered UUID index."""
    result: dict[UUID, T] = {}
    for item in items:
        if item.id in result:
            raise IdentityConflictError(f"duplicate {kind} UUID {item.id}")
        result[item.id] = item
    return MappingProxyType(result)


def unique_index(
    items: Iterable[T],
    key: Callable[[T], K | None],
    kind: str,
) -> Mapping[K, UUID]:
    """Index unique semantic keys by UUID, omitting ``None`` keys."""
    result: dict[K, UUID] = {}
    for item in items:
        value = key(item)
        if value is None:
            continue
        if value in result:
            raise ValueError(f"{kind} must be unique: {value!r}")
        result[value] = item.id
    return MappingProxyType(result)


def multi_index(
    items: Iterable[T],
    key: Callable[[T], K | None],
) -> Mapping[K, tuple[UUID, ...]]:
    """Index potentially repeated semantic keys by UUID in insertion order."""
    result: dict[K, list[UUID]] = {}
    for item in items:
        value = key(item)
        if value is not None:
            result.setdefault(value, []).append(item.id)
    return MappingProxyType({value: tuple(ids) for value, ids in result.items()})
