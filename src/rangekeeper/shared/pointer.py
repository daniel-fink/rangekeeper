"""JSON Pointer paths (RFC 6901) for diagnostics and difference reports."""


def escape(token: object) -> str:
    """Return one reference token, with ``~`` and ``/`` escaped."""
    return str(token).replace("~", "~0").replace("/", "~1")


def child(path: str, *tokens: object) -> str:
    """Return the pointer that adds each token below ``path``."""
    return path + "".join("/" + escape(token) for token in tokens)
