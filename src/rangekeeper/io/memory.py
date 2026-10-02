"""Thread-safe append-only storage for immutable document revisions."""

from threading import RLock
from uuid import UUID

from ..errors import MissingReferenceError
from ..validate import require_uuid
from ..run.validation import validate as validate_run
from ._document import snapshot, require_same, require_revision
from .store import Document, D, Model, Specification, Run


class MemoryStore:
    """An in-memory revision store; stored snapshots never track caller mutations."""

    def __init__(self) -> None:
        self._documents: dict[UUID, Document] = {}
        self._lock = RLock()

    def put(self, document: Document) -> UUID:
        """Revalidate, resolve Run dependencies, then publish or reject a conflict.

        The lock covers checking and publication. Identical writes retain the first
        stored representation; validation failure leaves the store unchanged.
        """
        candidate = snapshot(document)
        with self._lock:
            if candidate.id in self._documents:
                require_same(self._documents[candidate.id], candidate)
            if isinstance(candidate, Run):
                validate_run(candidate, resolver=self).raise_if_invalid()
            self._documents.setdefault(candidate.id, candidate)
        return candidate.id

    def _load(self, id: UUID, kind: type[D]) -> D:
        require_uuid(id, "id")
        with self._lock:
            try:
                document = self._documents[id]
            except KeyError as error:
                raise MissingReferenceError(str(id)) from error
            return require_revision(document, id, kind)

    def load_model(self, id: UUID) -> Model:
        """Return the exact Model snapshot, or raise for missing/wrong-kind identity."""
        return self._load(id, Model)

    def load_specification(self, id: UUID) -> Specification:
        """Return a saved contribution; do not resolve its includes or Model pin."""
        return self._load(id, Specification)

    def load_run(self, id: UUID) -> Run:
        """Return the finalized Run snapshot; never execute or revise it."""
        return self._load(id, Run)
