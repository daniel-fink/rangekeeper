"""Decode YAML with one policy for every Rangekeeper reader."""

from rangekeeper.shared.errors import DecodeError
from rangekeeper.shared.optional import requires

_TAGS = frozenset(
    "tag:yaml.org,2002:" + name
    for name in ("map", "seq", "str", "null", "bool", "int", "float", "timestamp")
)


def decode(content: str | bytes) -> object:
    """Decode safe, JSON-compatible YAML with unique string keys.

    Custom and executable tags and merge keys raise DecodeError. Timestamp
    scalars stay strings: only generated typed fields interpret dates. A shared
    alias decodes to the same object at each use; callers copy the result, which
    rejects cyclic aliases.
    """
    if not isinstance(content, (str, bytes)):
        raise TypeError("YAML content must be text or bytes")
    with requires("yaml"):
        import yaml

    class Loader(yaml.SafeLoader):
        def construct_object(self, node, deep=False):
            if node.tag not in _TAGS:
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

    # This subclass has its own constructor table; SafeLoader's global behaviour
    # is unchanged for other callers, including external source readers.
    def timestamp(loader, node):
        return loader.construct_scalar(node)

    Loader.add_constructor("tag:yaml.org,2002:timestamp", timestamp)
    try:
        return yaml.load(content, Loader=Loader)
    except yaml.YAMLError as error:
        raise DecodeError(f"invalid YAML: {error}") from error
