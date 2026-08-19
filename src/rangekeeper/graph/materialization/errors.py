class MaterializationError(Exception):
    """Base class for materialization failures."""


class SnapshotError(MaterializationError, ValueError):
    """Raised when Snapshot records are malformed or internally inconsistent."""


class UnsupportedValueError(MaterializationError, TypeError):
    """Raised when a feature value has no portable materialization encoding."""
