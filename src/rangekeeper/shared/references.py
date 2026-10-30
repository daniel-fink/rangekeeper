"""Read-only revision lookup contracts, independent of storage and transport.

Resolvers return the exact requested UUID and document kind. Missing revisions raise
MissingReferenceError; wrong kinds raise ReferenceTypeError. Domain code never
implicitly contacts a service or imports a filesystem implementation.
"""

from typing import TYPE_CHECKING, Protocol, TypeVar
from uuid import UUID

from rangekeeper.shared.errors import IdentityConflictError, ReferenceTypeError

if TYPE_CHECKING:
    from rangekeeper.model.model import Model
    from rangekeeper.run.run import Run
    from rangekeeper.specification.specification import Specification

# A document kind that a lookup requests.
K = TypeVar("K")


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


def require_revision(document: object, identity: UUID, kind: type[K]) -> K:
    """Return a document that a lookup read, after checking its UUID and kind.

    A document with another UUID raises IdentityConflictError, and one of
    another kind ReferenceTypeError.
    """
    if getattr(document, "id", None) != identity:
        raise IdentityConflictError(
            f"stored revision does not match requested UUID {identity}"
        )
    if not isinstance(document, kind):
        raise ReferenceTypeError(
            f"{identity} is {type(document).__name__}, expected {kind.__name__}"
        )
    return document
