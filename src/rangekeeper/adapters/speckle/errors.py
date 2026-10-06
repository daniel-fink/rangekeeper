"""Transport failures are distinct from invalid domain mappings."""


class TransportError(RuntimeError):
    """The explicit remote read could not complete; no Model was constructed."""


class MappingError(ValueError):
    """Invalid transport content with its source path and optional domain identity."""

    def __init__(self, message: str, *, path: str = "/", identity: str | None = None):
        self.path, self.identity = path, identity
        super().__init__(f"{path}: {message}" + (f" [{identity}]" if identity else ""))
