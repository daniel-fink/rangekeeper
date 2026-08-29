from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from .errors import (
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


def catalog_values(values: Iterable[C] | Mapping[str, C]) -> tuple[C, ...]:
    """Normalize catalog constructor input without iterating mapping keys."""
    return tuple(values.values() if isinstance(values, Mapping) else values)


@dataclass(frozen=True, slots=True, repr=False)
class Catalog(Mapping[str, C], Generic[C]):
    """Immutable, insertion-ordered definitions keyed by code."""

    _values: tuple[C, ...]
    kind: str
    scope: str | None = field(default=None, repr=False)
    _values_by_id: Mapping[UUID, C] = field(init=False, repr=False, compare=False)
    _by_code: Mapping[str, C] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        values = tuple(self._values)
        by_id = index_by_id(values, self.kind)
        by_code: dict[str, C] = {}
        for value in values:
            if value.code in by_code:
                raise ValueError(f"{self.kind} codes must be unique: {value.code!r}")
            by_code[value.code] = value
        object.__setattr__(self, "_values", values)
        object.__setattr__(self, "_values_by_id", by_id)
        object.__setattr__(self, "_by_code", MappingProxyType(by_code))

    def __getitem__(self, code: str) -> C:
        if not isinstance(code, str):
            raise TypeError(f"{self.kind} code must be a string")
        try:
            return self._by_code[code]
        except KeyError as error:
            raise UnknownDefinitionError(self.kind, code, scope=self.scope) from error

    def __iter__(self) -> Iterator[str]:
        return iter(self._by_code)

    def __len__(self) -> int:
        return len(self._by_code)

    def __repr__(self) -> str:
        return repr(dict(self.items()))

    def _by_identifier(self, identifier: UUID) -> C:
        if not isinstance(identifier, UUID):
            raise TypeError(f"{self.kind} id must be a UUID")
        try:
            return self._values_by_id[identifier]
        except KeyError as error:
            raise UnknownDefinitionError(
                self.kind, identifier, scope=self.scope
            ) from error

    def _canonical(self, value: C) -> C:
        if not hasattr(value, "id"):
            raise TypeError(f"value must be a {self.kind}")
        canonical = self._values_by_id.get(value.id)
        if canonical is None:
            raise UnknownDefinitionError(self.kind, value.id, scope=self.scope)
        if canonical is not value:
            raise NonCanonicalDefinitionError(self.kind, value.id, scope=self.scope)
        return canonical

    def _contains_identifier(self, identifier: UUID) -> bool:
        return identifier in self._values_by_id


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
