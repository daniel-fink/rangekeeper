class AdapterError(Exception):
    """Base class for graph adapter failures."""


class AdapterEncodingError(AdapterError, ValueError):
    """Raised when an adapter cannot encode or decode its boundary format."""


class SpeckleImportError(AdapterError, ValueError):
    """Raised when a Speckle object graph cannot be imported."""


class SpeckleConflictError(SpeckleImportError):
    """Raised when duplicate Speckle representations conflict."""
