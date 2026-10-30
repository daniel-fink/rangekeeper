"""Local filesystem revision storage using atomic no-overwrite publication."""

import json as _json
from collections.abc import Iterator
from os import PathLike
from pathlib import Path
from uuid import UUID

from rangekeeper.io._atomic import write_new
from rangekeeper.io._document import (
    Document,
    Model,
    Paths,
    Run,
    Specification,
    envelope,
    from_envelope,
    require_revision,
    require_same,
    trusted,
)
from rangekeeper.io._runs import find_runs
from rangekeeper.io.json import _parse
from rangekeeper.run.validation import validate as validate_run
from rangekeeper.run.validation import validated_in
from rangekeeper.shared.arguments import require_uuid
from rangekeeper.shared.errors import DecodeError, MissingReferenceError

__all__ = ["DirectoryStore"]


class DirectoryStore:
    """Append-only UUID files on a filesystem supporting hard links and file fsync.

    ``path`` is the folder of the files, such as ``DirectoryStore(path="runs")``;
    a relative path is relative to the working folder at construction. The
    first put creates the folder. Construction performs no IO. Readers validate envelopes/content on every load.
    External edits/deletion are outside this store's immutability contract. There is
    no multi-document transaction; a Run is published after its dependencies.
    """

    def __init__(self, path: str | PathLike[str]) -> None:
        self._root = Path(path).absolute()

    @property
    def root(self) -> Path:
        """Absolute storage location; constructing the store does not create it."""
        return self._root

    def _read(self, id: UUID) -> Document:
        document = from_envelope(_parse(self._text(id)))
        return require_revision(document, id, type(document))

    def _text(self, id: UUID) -> str:
        """Return the text of the file of revision ``id``."""
        require_uuid(id, "id")
        try:
            return (self.root / f"{id}.json").read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise MissingReferenceError(
                id, kind="document", where=f"DirectoryStore {self.root}"
            ) from error
        except UnicodeError as error:
            raise DecodeError(str(error)) from error

    def _ids(self) -> list[UUID]:
        """Return the UUID of each stored revision, in UUID order.

        A file whose name is not ``<UUID>.json``, such as the temporary file
        of an interrupted put, is not a revision.
        """
        if not self.root.is_dir():
            return []
        found = (_identity(entry.name) for entry in self.root.iterdir())
        return sorted((id for id in found if id is not None), key=str)

    def _runs(self) -> Iterator[Run]:
        """Read and validate each stored Run, in UUID order; skip other kinds."""
        for id in self._ids():
            data = _parse(self._text(id))
            if isinstance(data, dict) and data.get("kind") == Run.__name__:
                yield require_revision(from_envelope(data), id, Run)

    def put(self, document: Document) -> UUID:
        """Atomically add a validated revision, or compare it with the stored one.

        The document was validated when it was built; put does not validate it
        again. A Run's references are resolved against this store first, unless
        the Run already passed that validation against this store
        (``run.validation.mark_validated``) and every revision that the
        validation read from elsewhere is now in this store.

        Identical concurrent puts succeed; different content/kind conflicts. A crash
        before the final link can leave only a temporary file, ignored by readers.
        IO failure after linking may leave a complete published record; retries are
        idempotent. No overwrite rename or cross-document transaction is used.
        """
        candidate = trusted(document)
        try:
            existing = self._read(candidate.id)
        except MissingReferenceError:
            existing = None
        if existing is not None:
            require_same(existing, candidate)
        if isinstance(candidate, Run) and not validated_in(
            candidate, self, lambda id: (self.root / f"{id}.json").exists()
        ):
            validate_run(run=candidate, resolver=self).raise_if_invalid()
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

    def load_paths(self, id: UUID) -> Paths:
        """Read and validate the exact market paths revision; never draw again."""
        return require_revision(self._read(id), id, Paths)

    def find_runs(self, *, specification: str) -> tuple[Run, ...]:
        """Return the Runs of the Specifications named ``specification``.

        The store reads and validates each stored Run, and the Specification
        of each. The Runs come in the order of their recorded finish times,
        earliest first, so ``[-1]`` is the Run that finished last. A batch Run
        takes the latest finish time of its cases. A Run without a time comes
        first, and Runs with the same time are in UUID order. The result can
        be empty.
        """
        return find_runs(self._runs(), specification=specification, resolver=self)


def _identity(name: str) -> UUID | None:
    """Return the UUID of a revision file name ``<UUID>.json``, else None."""
    stem, suffix = name[:-5], name[-5:]
    if suffix != ".json":
        return None
    try:
        identity = UUID(stem)
    except ValueError:
        return None
    return identity if f"{identity}.json" == name else None
