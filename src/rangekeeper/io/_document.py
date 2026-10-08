"""Small document-kind dispatch shared by codecs and stores; no field definitions."""

from collections.abc import Mapping
from uuid import UUID
from typing import cast

from rangekeeper.shared.errors import (
    DecodeError,
    IdentityConflictError,
    ReferenceTypeError,
    RevisionConflictError,
)
from rangekeeper.io.store import Document, D, Model, Specification, Run

KINDS: dict[str, type[Document]] = {
    kind.__name__: kind for kind in (Model, Specification, Run)
}


def require_kind(kind: object) -> None:
    """Accept an explicit public root facade, excluding derived views and raw records."""
    if kind not in (Model, Specification, Run):
        raise TypeError("kind must be Model, Specification, or Run")


def restore(data: object, kind: type[D]) -> D:
    """Construct through the facade, retaining structural/semantic/version errors."""
    require_kind(kind)
    return cast(D, kind.from_data(cast(Mapping[str, object], data)))


def snapshot(document: Document) -> Document:
    """Revalidate detached content before any IO; do not trust a caller-owned instance."""
    require_kind(type(document))
    restored = restore(document.to_data(), type(document))
    if restored.id != document.id:
        raise IdentityConflictError(
            "document identity differs from serialized Metadata"
        )
    return restored


def require_revision(document: Document, identity: UUID, kind: type[D]) -> D:
    """Verify both the requested revision and kind after decoding."""
    if document.id != identity:
        raise IdentityConflictError(
            f"stored revision does not match requested UUID {identity}"
        )
    if not isinstance(document, kind):
        raise ReferenceTypeError(
            f"{identity} is {type(document).__name__}, expected {kind.__name__}"
        )
    return document


def require_same(existing: Document, candidate: Document) -> None:
    """Compare schema-directed content, never changing stored encounter order."""
    left = existing._record if isinstance(existing, Model) else existing.record
    right = candidate._record if isinstance(candidate, Model) else candidate.record
    if type(existing) is not type(candidate) or not left.equivalent(right):
        raise RevisionConflictError(
            f"different content or kind for revision {candidate.id}"
        )


def envelope(document: Document) -> dict:
    """Return the store-only kind envelope; codecs never emit this wrapper."""
    return {"kind": type(document).__name__, "document": document.to_data()}


def from_envelope(data: object) -> Document:
    """Decode a closed storage envelope through its declared document factory."""
    if not isinstance(data, dict) or set(data) != {"kind", "document"}:
        raise DecodeError("storage requires exactly kind and document")
    kind = data["kind"]
    if not isinstance(kind, str) or kind not in KINDS:
        raise DecodeError("unknown stored document kind")
    return restore(data["document"], KINDS[kind])
