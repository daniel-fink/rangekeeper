class GraphError(Exception):
    """Base class for graph-domain errors."""


class IdentityConflictError(GraphError, ValueError):
    """Raised when one stable ID is assigned to different objects."""


class MissingEntityError(GraphError, KeyError):
    """Raised when an entity ID is not registered in a Model."""


class MissingRelationshipError(GraphError, KeyError):
    """Raised when a relationship ID is not registered in a Model."""


class InvalidAssemblyError(GraphError, ValueError):
    """Raised when proposed Assembly contents violate graph invariants."""
