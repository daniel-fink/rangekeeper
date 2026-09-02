from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from .errors import (
    CatalogInstanceError,
    IdentityConflictError,
    UnknownDefinitionError,
    )


class CodedIdentified(Protocol):
    id: UUID
    code: str


C = TypeVar("C", bound=CodedIdentified)


@dataclass(frozen=True, slots=True, repr=False, eq=False, init=False)
class Catalog(Mapping[str, C], Generic[C]):
    """Immutable, insertion-ordered definitions keyed by code."""

    _by_code: Mapping[str, C] = field(repr=False, compare=False)
    _by_id: Mapping[UUID, C] = field(repr=False, compare=False)
    kind: str
    scope: str | None = field(default=None, repr=False)

    def __init__(
        self,
        values: Iterable[C],
        kind: str,
        scope: str | None = None,
    ) -> None:
        items = tuple(values)
        by_id: dict[UUID, C] = {}
        for value in items:
            if value.id in by_id:
                raise IdentityConflictError(f"duplicate {kind} UUID {value.id}")
            by_id[value.id] = value
        by_code: dict[str, C] = {}
        for value in items:
            if value.code in by_code:
                raise ValueError(f"{kind} codes must be unique: {value.code!r}")
            by_code[value.code] = value
        object.__setattr__(self, "_by_code", MappingProxyType(by_code))
        object.__setattr__(self, "_by_id", MappingProxyType(by_id))
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "scope", scope)

    @classmethod
    def from_input(
        cls,
        values: Iterable[C] | Mapping[str, C],
        *,
        item_type: type[C],
        field: str,
        kind: str,
        scope: str | None = None,
    ) -> Catalog[C]:
        """Validate and normalize iterable or code-keyed catalog input."""
        items = tuple(values.values() if isinstance(values, Mapping) else values)
        if any(not isinstance(item, item_type) for item in items):
            raise TypeError(f"{field} must contain only {item_type.__name__} objects")
        if isinstance(values, Mapping):
            for code, item in values.items():
                if code != item.code:
                    raise ValueError(
                        f"{kind} mapping key {code!r} does not match "
                        f"{kind} code {item.code!r}"
                    )
        return cls(items, kind, scope)

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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return NotImplemented
        return dict(self.items()) == dict(other.items())

    def __hash__(self) -> int:
        return hash(frozenset(self.items()))

    def _lookup_id(self, identifier: UUID) -> C:
        if not isinstance(identifier, UUID):
            raise TypeError(f"{self.kind} id must be a UUID")
        try:
            return self._by_id[identifier]
        except KeyError as error:
            raise UnknownDefinitionError(
                self.kind, identifier, scope=self.scope
            ) from error

    def _contains_id(self, identifier: UUID) -> bool:
        return identifier in self._by_id

    def _require_catalog_instance(self, value: C) -> C:
        if not hasattr(value, "id"):
            raise TypeError(f"value must be a {self.kind}")
        registered = self._by_id.get(value.id)
        if registered is None:
            raise UnknownDefinitionError(self.kind, value.id, scope=self.scope)
        if registered is not value:
            raise CatalogInstanceError(self.kind, value.id, scope=self.scope)
        return registered