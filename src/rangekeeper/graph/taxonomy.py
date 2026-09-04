from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID, uuid4

from .. import validate
from ._catalog import Catalog
from .classification import Classification


__all__ = ["Taxonomy"]


@dataclass(frozen=True, slots=True, init=False)
class Taxonomy:
    """An immutable, single-root classification hierarchy."""

    id: UUID
    code: str
    name: str
    classifications: Catalog[Classification]
    definition: str | None
    _root_id: UUID = field(init=False, repr=False, compare=False)
    _children_by_parent_id: Mapping[UUID, tuple[Classification, ...]] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __init__(
        self,
        *,
        code: str,
        name: str,
        classifications: Iterable[Classification] | Mapping[str, Classification],
        id: UUID | None = None,
        definition: str | None = None,
    ) -> None:
        identifier = uuid4() if id is None else id
        validate.require_uuid(identifier, "id")
        validate.require_text(code, "Taxonomy.code")
        validate.require_text(name, "Taxonomy.name")
        validate.optional_text(definition, "definition")
        catalog = Catalog.from_input(
            classifications,
            item_type=Classification,
            field="classifications",
            kind="classification",
            scope=f"taxonomy {code!r}",
        )

        object.__setattr__(self, "id", identifier)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "classifications", catalog)
        object.__setattr__(self, "definition", definition)
        self._validate()

    def _validate(self) -> None:
        """Build hierarchy indexes while validating parents without a graph library."""

        classifications = tuple(self.classifications.values())
        roots = tuple(item for item in classifications if item.parent is None)
        if len(roots) != 1:
            raise ValueError("taxonomy must contain exactly one root")
        root = roots[0]
        children: dict[UUID, list[Classification]] = {}
        for item in classifications:
            if item.parent is None:
                continue
            if not self.classifications._contains_id(item.parent.id):
                raise ValueError(
                    f"classification {item.code!r} references a missing parent"
                )
            registered_parent = self.classifications._by_id_lookup(item.parent.id)
            if registered_parent is not item.parent:
                raise ValueError(
                    f"classification {item.code!r} parent is not the registered "
                    "taxonomy instance"
                )
            children.setdefault(item.parent.id, []).append(item)

        for item in classifications:
            current = item
            seen: set[UUID] = set()
            while current.parent is not None:
                if current.id in seen:
                    raise ValueError(
                        "taxonomy classifications must form an acyclic hierarchy"
                    )
                seen.add(current.id)
                current = current.parent
            if current is not root:
                raise ValueError("all classifications must descend from the root")

        object.__setattr__(self, "_root_id", root.id)
        object.__setattr__(
            self,
            "_children_by_parent_id",
            MappingProxyType(
                {identifier: tuple(items) for identifier, items in children.items()}
            ),
        )

    @property
    def root(self) -> Classification:
        """Return the hierarchy's sole root classification."""

        return self.classifications._by_id_lookup(self._root_id)

    def children(self, classification: Classification) -> tuple[Classification, ...]:
        """Return direct children in declaration order."""

        canonical = self.classifications._require_instance(classification)
        return self._children_by_parent_id.get(canonical.id, ())

    def ancestors(self, classification: Classification) -> tuple[Classification, ...]:
        """Return ancestors from root to immediate parent."""

        current = self.classifications._require_instance(classification).parent
        result: list[Classification] = []
        while current is not None:
            result.append(current)
            current = current.parent
        return tuple(reversed(result))

    def descendants(self, classification: Classification) -> tuple[Classification, ...]:
        """Return descendants in declaration-preserving preorder."""

        canonical = self.classifications._require_instance(classification)
        result: list[Classification] = []
        pending = list(reversed(self.children(canonical)))
        while pending:
            item = pending.pop()
            result.append(item)
            pending.extend(reversed(self.children(item)))
        return tuple(result)

    def is_a(
        self,
        classification: Classification,
        ancestor: Classification,
    ) -> bool:
        """Return whether a classification equals or descends from the ancestor."""

        current: Classification | None = self.classifications._require_instance(
            classification
        )
        canonical_ancestor = self.classifications._require_instance(ancestor)
        while current is not None:
            if current is canonical_ancestor:
                return True
            current = current.parent
        return False
