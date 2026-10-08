"""Strict JSON interchange for public domain documents, with no storage envelope."""

import json as _json
from pathlib import Path

from rangekeeper.schema.runtime import _json_copy
from rangekeeper.shared.errors import DecodeError
from rangekeeper.io._atomic import write_new
from rangekeeper.io._document import restore, require_kind, snapshot
from rangekeeper.io.store import Document, D


def _parse(text: str) -> object:
    """Reject duplicate keys and non-JSON numbers at every depth, including opaque data."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise DecodeError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise DecodeError(f"non-JSON number: {value}")

    try:
        return _json_copy(
            _json.loads(text, object_pairs_hook=unique, parse_constant=constant)
        )
    except (ValueError, TypeError) as error:
        raise DecodeError(str(error)) from error


def loads(text: str, *, kind: type[D]) -> D:
    """Decode and locally validate an explicit root kind; resolve no external inputs.

    Malformed/ambiguous text raises DecodeError; valid JSON with an invalid document
    retains its ValidationError or version/domain error. There is no kind guessing.
    """
    require_kind(kind)
    return restore(_parse(text), kind)


def dumps(document: Document) -> str:
    """Revalidate and export detached JSON, retaining encounter order and presence."""
    return (
        _json.dumps(
            snapshot(document).to_data(), ensure_ascii=False, allow_nan=False, indent=2
        )
        + "\n"
    )


def read(path: Path, *, kind: type[D]) -> D:
    """Read UTF-8; filesystem errors propagate and malformed text raises DecodeError."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeError as error:
        raise DecodeError(str(error)) from error
    return loads(text, kind=kind)


def write(document: Document, path: Path) -> Path:
    """Atomically create a new file; never replace an existing destination."""
    return write_new(Path(path), dumps(document))
