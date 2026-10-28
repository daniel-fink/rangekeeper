"""Thread-safe append-only storage for immutable document revisions."""

from threading import RLock
from uuid import UUID

from rangekeeper.io._document import (
    D,
    Document,
    Model,
    Run,
    Specification,
    require_revision,
    require_same,
    trusted,
)
from rangekeeper.run.validation import validate as validate_run
from rangekeeper.shared.arguments import require_uuid
from rangekeeper.shared.errors import MissingReferenceError


class MemoryStore:
    """An in-memory revision store of immutable, validated documents."""

    def __init__(self) -> None:
        self._documents: dict[UUID, Document] = {}
        self._lock = RLock()

    def put(self, document: Document) -> UUID:
        """Resolve Run dependencies, then publish or reject a conflict.

        The document was validated when it was built; put does not validate it
        again.

        The lock covers checking and publication. Identical writes retain the first
        stored representation; validation failure leaves the store unchanged.
        """
        candidate = trusted(document)
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
                raise MissingReferenceError(
                    id, kind=kind.__name__, where="MemoryStore"
                ) from error
            return require_revision(document, id, kind)

    def load_model(self, id: UUID) -> Model:
        """Return the exact Model revision, or raise for missing/wrong-kind identity."""
        return self._load(id, Model)

    def load_specification(self, id: UUID) -> Specification:
        """Return a saved contribution; do not resolve its includes or Model pin."""
        return self._load(id, Specification)

    def load_run(self, id: UUID) -> Run:
        """Return the finalized Run; never execute or revise it."""
        return self._load(id, Run)
