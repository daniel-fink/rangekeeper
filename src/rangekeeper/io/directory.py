"""Local filesystem revision storage using atomic no-overwrite publication."""

import json as _json
from pathlib import Path
from uuid import UUID

from rangekeeper.shared.errors import MissingReferenceError, DecodeError
from rangekeeper.shared.arguments import require_uuid
from rangekeeper.run.validation import validate as validate_run
from rangekeeper.io._atomic import write_new
from rangekeeper.io._document import (
    snapshot,
    require_same,
    require_revision,
    envelope,
    from_envelope,
)
from rangekeeper.io.json import _parse
from rangekeeper.io.store import Document, D, Model, Specification, Run


class DirectoryStore:
    """Append-only UUID files on a filesystem supporting hard links and file fsync.

    Construction performs no IO. Readers validate envelopes/content on every load.
    External edits/deletion are outside this store's immutability contract. There is
    no multi-document transaction; a Run is published after its dependencies.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root).absolute()

    @property
    def root(self) -> Path:
        """Absolute storage location; constructing the store does not create it."""
        return self._root

    def _read(self, id: UUID) -> Document:
        require_uuid(id, "id")
        try:
            text = (self.root / f"{id}.json").read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise MissingReferenceError(str(id)) from error
        except UnicodeError as error:
            raise DecodeError(str(error)) from error
        document = from_envelope(_parse(text))
        return require_revision(document, id, type(document))

    def put(self, document: Document) -> UUID:
        """Validate before creating storage; atomically add a revision or compare it.

        Identical concurrent puts succeed; different content/kind conflicts. A crash
        before the final link can leave only a temporary file, ignored by readers.
        IO failure after linking may leave a complete published record; retries are
        idempotent. No overwrite rename or cross-document transaction is used.
        """
        candidate = snapshot(document)
        try:
            existing = self._read(candidate.id)
        except MissingReferenceError:
            existing = None
        if existing is not None:
            require_same(existing, candidate)
        if isinstance(candidate, Run):
            validate_run(candidate, resolver=self).raise_if_invalid()
        if existing is not None:
            return candidate.id
        text = (
            _json.dumps(
                envelope(candidate), ensure_ascii=False, allow_nan=False, indent=2
            )
            + "\n"
        )
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            write_new(self.root / f"{candidate.id}.json", text)
        except FileExistsError:
            require_same(self._read(candidate.id), candidate)
        return candidate.id

    def load_model(self, id: UUID) -> Model:
        """Read, validate and verify the exact requested Model revision."""
        return require_revision(self._read(id), id, Model)

    def load_specification(self, id: UUID) -> Specification:
        """Read a locally valid contribution; leave external resolution explicit."""
        return require_revision(self._read(id), id, Specification)

    def load_run(self, id: UUID) -> Run:
        """Read a locally valid finalized Run without recursively loading its tree."""
        return require_revision(self._read(id), id, Run)
