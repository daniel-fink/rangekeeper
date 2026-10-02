"""Publish complete UTF-8 files atomically without overwriting existing names."""

import errno
import os
from pathlib import Path
import tempfile


def write_new(path: Path, text: str) -> Path:
    """Flush a same-directory temporary file and publish it with a no-overwrite link.

    The parent must exist. Unsupported link operations and filesystem failures
    propagate as OSError. A failure before linking leaves no final file; a failure
    syncing the directory after publication can leave the complete final file.
    Callers may safely inspect/retry, but no cross-file transaction is promised.
    """
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        # link fails with FileExistsError if a concurrent writer published first.
        os.link(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    _sync_directory(path.parent)
    return path


def _sync_directory(path: Path) -> None:
    """Persist the directory entry where the local filesystem supports fsync."""
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        if error.errno not in (errno.EINVAL, errno.ENOTSUP):
            raise
