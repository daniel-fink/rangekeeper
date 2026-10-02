"""Read-only revision lookup contracts, independent of storage and transport.

Resolvers return the exact requested UUID and document kind. Missing revisions raise
MissingReferenceError; wrong kinds raise ReferenceTypeError. Domain code never
implicitly contacts a service or imports a filesystem implementation.
"""

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from .model.model import Model
    from .specification.specification import Specification
    from .run.run import Run


class SpecificationResolver(Protocol):
    """Read dependency for investigations, with no unnecessary Run/store operations."""

    def load_model(self, id: UUID) -> "Model":
        """Return one pinned Model revision without searching predecessors."""
        ...

    def load_specification(self, id: UUID) -> "Specification":
        """Return one pinned Specification contribution or batch."""
        ...


class DocumentResolver(SpecificationResolver, Protocol):
    """Typed revision lookup for all three saved document kinds."""

    def load_run(self, id: UUID) -> "Run":
        """Return a locally valid finalized Run without executing it."""
        ...
