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


class AmbiguousDefinitionError(AmbiguousLookupError):
    """Raised when an unscoped definition code has multiple matches."""

    def __init__(
        self,
        kind: str,
        reference: object,
        matches: int,
        *,
        scope: str | None = None,
    ) -> None:
        self.kind = kind
        self.reference = reference
        self.matches = matches
        self.scope = scope
        location = "" if scope is None else f" in {scope}"
        super().__init__(f"ambiguous {kind} {reference!r}{location}: {matches} matches")


class NonCanonicalDefinitionError(GraphError, ValueError):
    """Raised when an object is not the registered instance for its UUID."""

    def __init__(
        self, kind: str, identifier: object, *, scope: str | None = None
    ) -> None:
        self.kind = kind
        self.identifier = identifier
        self.scope = scope
        location = "" if scope is None else f" in {scope}"
        super().__init__(f"{kind} {identifier!r} is not canonical{location}")


class MissingEntityError(GraphError, KeyError):
    """Raised when an entity ID is not registered in a Graph."""


class MissingRelationshipError(GraphError, KeyError):
    """Raised when a relationship ID is not registered in a Graph."""


class InvalidAssemblyError(GraphError, ValueError):
    """Raised when proposed Assembly contents violate graph invariants."""


class InvalidAggregationError(GraphError, ValueError):
    """Raised when a View or aggregation request cannot be aggregated safely."""
