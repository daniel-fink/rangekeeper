"""Tabular projection for the immutable graph core.

Snapshot and value serialization are intentionally deferred to schema v3.
"""

from .errors import (
    MaterializationError,
    SnapshotError,
    TableError,
    UnsupportedValueError,
)
from .table import Table

__all__ = [
    "MaterializationError",
    "SnapshotError",
    "Table",
    "TableError",
    "UnsupportedValueError",
]
