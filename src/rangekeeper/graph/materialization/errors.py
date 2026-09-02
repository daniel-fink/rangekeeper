class MaterializationError(Exception):
    """Base class for materialization failures."""


class TableError(MaterializationError, ValueError):
    """Raised when a tabular projection or grouping request is invalid."""
