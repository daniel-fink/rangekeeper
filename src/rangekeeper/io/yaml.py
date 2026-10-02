"""Optional safe YAML codec for the same JSON-compatible domain content."""

from pathlib import Path
from importlib import import_module

from .._records import _json_copy
from ..errors import DecodeError
from ._atomic import write_new
from ._document import restore, require_kind, snapshot
from .store import Document, D


def _implementation():
    """Import the optional dependency only when a YAML operation is requested."""
    try:
        yaml = import_module("yaml")
    except ImportError as error:
        raise ImportError("YAML IO requires rangekeeper[yaml]") from error
    return yaml


def loads(text: str, *, kind: type[D]) -> D:
    """Decode safe JSON-compatible YAML with unique string keys and explicit kind.

    Merge keys, executable/custom tags, cyclic aliases and non-finite numbers are
    rejected. Timestamp scalars remain strings: only generated typed fields interpret
    date/time/UUID meaning, and opaque Claim content is never recursively coerced.
    Shared non-cyclic aliases are copied into independent immutable data.
    """
    require_kind(kind)
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    yaml = _implementation()

    # PyYAML remains a lazy optional module; the base is only known at runtime.
    class Loader(yaml.SafeLoader):  # type: ignore[name-defined]
        def construct_object(self, node, deep=False):
            allowed = {"map", "seq", "str", "null", "bool", "int", "float", "timestamp"}
            if node.tag not in {"tag:yaml.org,2002:" + name for name in allowed}:
                raise DecodeError(f"unsupported YAML tag: {node.tag}")
            return super().construct_object(node, deep=deep)

        def construct_mapping(self, node, deep=False):
            result = {}
            for key_node, value_node in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    raise DecodeError("YAML merge keys are unsupported")
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, str):
                    raise DecodeError("YAML keys must be strings")
                if key in result:
                    raise DecodeError(f"duplicate YAML key: {key}")
                result[key] = self.construct_object(value_node, deep=deep)
            return result

    # This subclass has its own constructor table; SafeLoader's global behavior
    # is unchanged for other callers, including legacy workflow adapters.
    Loader.add_constructor(
        "tag:yaml.org,2002:timestamp",
        lambda loader, node: loader.construct_scalar(node),
    )
    try:
        data = _json_copy(yaml.load(text, Loader=Loader))
    except (yaml.YAMLError, ValueError, TypeError, KeyError) as error:
        raise DecodeError(str(error)) from error
    return restore(data, kind)


def dumps(document: Document) -> str:
    """Write safe YAML retaining list order, absent/null fields and string scalars."""
    return _implementation().safe_dump(
        snapshot(document).to_data(), sort_keys=False, allow_unicode=True
    )


def read(path: Path, *, kind: type[D]) -> D:
    """Read UTF-8 without resolving referenced revisions; OSError remains visible."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeError as error:
        raise DecodeError(str(error)) from error
    return loads(text, kind=kind)


def write(document: Document, path: Path) -> Path:
    """Atomically create new YAML; require an existing parent and absent destination."""
    return write_new(Path(path), dumps(document))
