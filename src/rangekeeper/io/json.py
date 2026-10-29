"""Strict JSON interchange for public domain documents, with no storage envelope."""

import json as _json
from pathlib import Path

from rangekeeper.io._amounts import amounts, strict
from rangekeeper.io._atomic import write_new
from rangekeeper.io._document import D, Document, require_kind, restore, trusted
from rangekeeper.schema.runtime import copy_json
from rangekeeper.shared.encoding import parse_json
from rangekeeper.shared.errors import DecodeError

__all__ = ["dumps", "loads", "read", "write"]


def _parse(text: str) -> object:
    """Parse with the shared JSON policy and copy the result as detached data."""
    data = parse_json(text)
    try:
        return copy_json(data)
    except (ValueError, TypeError) as error:
        raise DecodeError(str(error)) from error


def loads(*, text: str, kind: type[D]) -> D:
    """Decode and locally validate an explicit root kind; resolve no external inputs.

    Malformed/ambiguous text raises DecodeError; valid JSON with an invalid document
    retains its ValidationError or version/domain error. There is no kind guessing.
    A currency amount must be a string with its canonical text (ADR-023); the
    error for other text gives the canonical text.
    """
    require_kind(kind)
    return restore(amounts(kind.__name__, _parse(text), strict), kind)


def dumps(document: Document) -> str:
    """Export detached JSON, retaining encounter order and presence.

    The validated document is not validated again.
    """
    return (
        _json.dumps(
            trusted(document).to_data(), ensure_ascii=False, allow_nan=False, indent=2
        )
        + "\n"
    )


def read(*, path: Path, kind: type[D]) -> D:
    """Read UTF-8; filesystem errors propagate and malformed text raises DecodeError."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeError as error:
        raise DecodeError(str(error)) from error
    return loads(text=text, kind=kind)


def write(*, document: Document, path: Path) -> Path:
    """Atomically create a new file; never replace an existing destination."""
    return write_new(Path(path), dumps(document))
