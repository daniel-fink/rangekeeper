"""Publish complete UTF-8 files atomically without overwriting existing names."""

import errno
import os
from pathlib import Path
import tempfile


class PublishedFileError(OSError):
    """The complete file is visible, but its durability was not confirmed."""

    published = True

    def __init__(self, path: Path, error: OSError):
        self.path = path
        self.error = error
        super().__init__(
            error.errno,
            f"File published; durability was not confirmed: {error}",
            str(path),
        )


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
    return _write(path, text, replace=False)


def replace(path: Path, text: str) -> Path:
    """Replace a complete file; PublishedFileError means replacement occurred.

    A pre-publication failure preserves the old file. Never retry or roll back a
    published replacement without accounting for a possible subsequent writer.
    """
    return _write(path, text, replace=True)


def _write(path: Path, text: str, *, replace: bool) -> Path:
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
            if replace:
                os.replace(temporary_path, path)
            else:
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
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        if error.errno not in (errno.EINVAL, errno.ENOTSUP):
            raise
