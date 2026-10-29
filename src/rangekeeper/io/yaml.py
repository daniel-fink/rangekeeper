"""Optional safe YAML codec for the same JSON-compatible domain content."""

from pathlib import Path
from typing import Any

from rangekeeper.io._amounts import amounts, detach, lenient, numbers
from rangekeeper.io._atomic import write_new
from rangekeeper.io._document import D, Document, require_kind, restore, trusted
from rangekeeper.schema.runtime import copy_json
from rangekeeper.shared.errors import DecodeError
from rangekeeper.shared.optional import requires
from rangekeeper.shared.yaml import decode

__all__ = ["dumps", "loads", "read", "write"]


def _implementation() -> Any:
    """Import the optional dependency only when a YAML operation is requested."""
    with requires("yaml"):
        import yaml  # noqa: PLC0415 - optional dependency
    return yaml


def loads(*, text: str, kind: type[D]) -> D:
    """Decode safe JSON-compatible YAML with unique string keys and explicit kind.

    The policy is ``rangekeeper.shared.yaml.decode``. Cyclic aliases and
    non-finite numbers are also rejected; opaque Claim content is never
    recursively coerced. Shared non-cyclic aliases are copied into independent
    immutable data. A currency amount may be a quoted string or a plain
    numeral; it is read from its source text, never through float, and stored
    as canonical text (ADR-023).
    """
    require_kind(kind)
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    try:
        data = detach(decode(text, numerals=True))
        data = amounts(kind.__name__, data, lenient)
        data = copy_json(numbers(data))
    except DecodeError:
        raise
    except (ValueError, TypeError, KeyError) as error:
        raise DecodeError(str(error)) from error
    return restore(data, kind)


def dumps(document: Document) -> str:
    """Write safe YAML retaining list order, absent/null fields and string scalars.

    A currency amount is a quoted string with its canonical text.
    """
    return _implementation().safe_dump(
        trusted(document).to_data(), sort_keys=False, allow_unicode=True
    )


def read(*, path: Path, kind: type[D]) -> D:
    """Read UTF-8 without resolving referenced revisions; OSError remains visible."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeError as error:
        raise DecodeError(str(error)) from error
    return loads(text=text, kind=kind)


def write(*, document: Document, path: Path) -> Path:
    """Atomically create new YAML; require an existing parent and absent destination."""
    return write_new(Path(path), dumps(document))
