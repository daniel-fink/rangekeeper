from collections.abc import Iterable
from uuid import UUID


class SelectionError(ValueError):
    """A Model selection or Value selector disagrees with its declared scope."""


class HierarchyError(ValueError):
    """A selected graph is not one rooted tree; IDs identify the offending scope."""

    def __init__(self, code: str, message: str, *, ids: Iterable[UUID] = ()) -> None:
        self.code = code
        self.ids = tuple(ids)
        super().__init__(f"{code}: {message}; ids={self.ids}")


class AggregationError(ValueError):
    """A recorded-quantity reduction cannot produce a meaningful finite result."""

__all__ = [
    "SelectionError",
    "HierarchyError",
    "AggregationError",
    "AmbiguousLookupError",
    "CatalogInstanceError",
    "GraphDependencyError",
    "GraphError",
    "IdentityConflictError",
    "InvalidAggregationError",
    "InvalidAssemblyError",
    "MissingEntityError",
    "MissingFactError",
    "MissingRelationshipError",
    "UnknownDefinitionError",
]


class GraphError(Exception):
    """Base class for graph-domain errors."""


class IdentityConflictError(GraphError, ValueError):
    """Raised when one stable ID is assigned to different objects."""


class AmbiguousLookupError(GraphError, LookupError):
    """Raised when a singular semantic lookup has multiple matches."""


class UnknownDefinitionError(GraphError, KeyError):
    """Raised when a definition cannot be found in the requested scope."""

    def __init__(
        self, kind: str, reference: object, *, scope: str | None = None
    ) -> None:
        self.kind = kind
        self.reference = reference
        self.scope = scope
        location = "" if scope is None else f" in {scope}"
        super().__init__(f"unknown {kind} {reference!r}{location}")


class CatalogInstanceError(GraphError, ValueError):
    """Raised when an object is not the instance registered in a catalog."""

    def __init__(
        self, kind: str, identifier: object, *, scope: str | None = None
    ) -> None:
        self.kind = kind
        self.identifier = identifier
        self.scope = scope
        location = "" if scope is None else f" in {scope}"
        super().__init__(
            f"{kind} {identifier!r} is not the registered instance{location}"
        )


class MissingEntityError(GraphError, KeyError):
    """Raised when an entity ID is not registered in a Graph."""


class MissingRelationshipError(GraphError, KeyError):
    """Raised when a relationship ID is not registered in a Graph."""


class MissingFactError(GraphError, KeyError):
    """Raised when a Fact target ID is not registered in Provenance."""


class GraphDependencyError(GraphError, ValueError):
    """Raised when removal would leave references to a graph object."""

    def __init__(
        self,
        target_kind: str,
        target_id: UUID,
        *,
        relationship_ids: Iterable[UUID] = (),
        assembly_ids: Iterable[UUID] = (),
        fact_target_ids: Iterable[UUID] = (),
    ) -> None:
        self.target_kind = target_kind
        self.target_id = target_id
        self.relationship_ids = frozenset(relationship_ids)
        self.assembly_ids = frozenset(assembly_ids)
        self.fact_target_ids = frozenset(fact_target_ids)
        dependencies = []
        for label, identifiers in (
            ("relationships", self.relationship_ids),
            ("assemblies", self.assembly_ids),
            ("Fact targets", self.fact_target_ids),
        ):
            if identifiers:
                dependencies.append(f"{label}=[{_format_ids(identifiers)}]")
        detail = ", ".join(dependencies) or "unknown dependencies"
        super().__init__(f"cannot remove {target_kind} {target_id}; remaining {detail}")


class InvalidAssemblyError(GraphError, ValueError):
    """Raised when proposed Assembly contents violate graph invariants."""


class InvalidAggregationError(GraphError, ValueError):
    """Raised when a View or aggregation request cannot be aggregated safely."""


def _format_ids(ids: Iterable[UUID]) -> str:
    return ", ".join(str(item) for item in sorted(ids, key=str))


from ..errors import BoundaryError, EncodingError, ValueEncodingError
