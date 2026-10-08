"""Validated, immutable tree topology for traversal and recorded-value reduction."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from uuid import UUID
from rangekeeper.model import Assembly
from rangekeeper.shared.arguments import require_uuid
from rangekeeper.model.system.errors import HierarchyError
from rangekeeper.model.system.view import View


@unique
class HierarchyKind(Enum):
    RELATIONSHIPS = "relationships"
    MEMBERSHIP = "membership"


@dataclass(frozen=True, init=False)
class Hierarchy:
    """One rooted tree over exactly the selected Entities, without new domain edges.

    Relationship and membership constructors choose distinct edge meanings. All
    selected nodes must belong to the tree. Multiple parents and parallel edges
    are rejected instead of selecting an arbitrary path. Iterative traversal
    avoids a Python recursion limit on otherwise valid deep trees.
    """

    __slots__ = (
        "view",
        "root",
        "kind",
        "_children",
        "_parents",
        "_preorder",
        "_postorder",
    )
    view: View
    root: UUID
    kind: HierarchyKind
    _children: Mapping[UUID, tuple[UUID, ...]]
    _parents: Mapping[UUID, UUID | None]
    _preorder: tuple[UUID, ...]
    _postorder: tuple[UUID, ...]

    def __init__(self, view: View, *, membership_root: UUID | None = None) -> None:
        if not isinstance(view, View):
            raise TypeError("view must be a Model-backed View")
        ids = tuple(entity.id for entity in view.entities)
        if not ids:
            raise HierarchyError("empty", "a hierarchy requires at least one Entity")
        members = set(ids)
        if membership_root is None:
            edges = tuple((edge.source, edge.target) for edge in view.relationships)
        else:
            view.entity(membership_root)
            edges = tuple(
                (entity.id, child)
                for entity in view.entities
                if isinstance(entity, Assembly)
                for child in entity.entities or ()
                if child in members
            )
        parents: dict[UUID, UUID | None] = dict.fromkeys(ids)
        unordered: dict[UUID, set[UUID]] = {id: set() for id in ids}
        for source, target in edges:
            if target in unordered[source]:
                raise HierarchyError(
                    "parallel_edges",
                    "two edges identify the same parent/child pair",
                    ids=(source, target),
                )
            if parents[target] is not None:
                raise HierarchyError(
                    "multiple_parents",
                    "a selected node has more than one parent",
                    ids=(target,),
                )
            parents[target] = source
            unordered[source].add(target)
        # Child order follows the View, not UUID/set order or relationship order.
        positions = {id: i for i, id in enumerate(ids)}
        children = {
            id: tuple(sorted(items, key=positions.__getitem__))
            for id, items in unordered.items()
        }
        roots = tuple(id for id in ids if parents[id] is None)
        pending = list(roots)
        reached = set()
        while pending:
            node = pending.pop()
            reached.add(node)
            pending.extend(children[node])
        if len(reached) != len(ids):
            raise HierarchyError(
                "cycle",
                "selected edges contain a cycle",
                ids=(id for id in ids if id not in reached),
            )
        if len(roots) != 1:
            raise HierarchyError("disconnected", "expected exactly one root", ids=roots)
        root = roots[0]
        if membership_root is not None and root != membership_root:
            raise HierarchyError(
                "root_mismatch",
                "requested membership root is not the selected root",
                ids=(membership_root, root),
            )
        preorder, postorder = [], []
        stack = [(root, False)]
        while stack:
            node, visited = stack.pop()
            if visited:
                postorder.append(node)
            else:
                preorder.append(node)
                stack.append((node, True))
                stack.extend((child, False) for child in reversed(children[node]))
        for name, value in (
            ("view", view),
            ("root", root),
            (
                "kind",
                (
                    HierarchyKind.RELATIONSHIPS
                    if membership_root is None
                    else HierarchyKind.MEMBERSHIP
                ),
            ),
            ("_children", MappingProxyType(children)),
            ("_parents", MappingProxyType(parents)),
            ("_preorder", tuple(preorder)),
            ("_postorder", tuple(postorder)),
        ):
            object.__setattr__(self, name, value)

    @classmethod
    def from_relationships(cls, view: View) -> "Hierarchy":
        """Require one parent-to-child tree using the selected Relationships."""
        return cls(view)

    @classmethod
    def from_membership(cls, view: View, *, root: UUID) -> "Hierarchy":
        """Require one tree using selected Assembly membership; ignore Relationships.

        Include transitive members explicitly in the View when nesting is wanted.
        Shared descendants remain legal Model content but cannot have two parents
        within this hierarchy. This operation never invents Relationship records.
        """
        require_uuid(root, "root")
        return cls(view, membership_root=root)

    def children(self, id: UUID) -> tuple[UUID, ...]:
        """Return selected child IDs in View order, validating lookup scope."""
        self.view.entity(id)
        return self._children[id]

    def parent(self, id: UUID) -> UUID | None:
        """Return the sole parent, or None for this hierarchy's root."""
        self.view.entity(id)
        return self._parents[id]

    def preorder(self) -> tuple[UUID, ...]:
        """Return each selected Entity once, before its descendants."""
        return self._preorder

    def postorder(self) -> tuple[UUID, ...]:
        """Return each selected Entity once, after its descendants."""
        return self._postorder


__all__ = ["Hierarchy", "HierarchyKind"]
