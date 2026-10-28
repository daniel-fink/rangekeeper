"""Publish complete UTF-8 files atomically without overwriting existing names."""

import errno
import os
import tempfile
from pathlib import Path

from rangekeeper.shared.errors import PublishedFileError


class PublishedFileInterrupted(KeyboardInterrupt):
    """Cancellation after publication; the complete file is already visible."""

    published = True

    def __init__(self, path: Path, error: KeyboardInterrupt):
        self.path = path
        self.error = error
        super().__init__(f"File published; durability confirmation interrupted: {path}")


def write_new(path: Path, text: str) -> Path:
    """Flush a same-directory temporary file and publish it with a no-overwrite link.

    The parent must exist. Unsupported link operations and filesystem failures
    propagate as OSError. A failure before linking leaves no final file; a failure
    syncing the directory after publication raises PublishedFileError and leaves
    the complete final file visible.
    Callers may safely inspect/retry, but no cross-file transaction is promised.
    """
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    published = False
    try:
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            # link fails if a concurrent writer published this name first.
            os.link(temporary_path, path)
            published = True
        finally:
            temporary_path.unlink(missing_ok=True)
        _sync_directory(path.parent)
    except OSError as error:
        if published:
            raise PublishedFileError(path, error) from error
        raise
    except KeyboardInterrupt as error:
        if published:
            raise PublishedFileInterrupted(path, error) from error
        raise
    return path


def _sync_directory(path: Path) -> None:
    """Persist the directory entry where the local filesystem supports fsync."""
    if os.name == "nt":
        # Windows cannot open a directory for fsync; NTFS journals the entry.
        return
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        if error.errno not in (errno.EINVAL, errno.ENOTSUP):
            raise
