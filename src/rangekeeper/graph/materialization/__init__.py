"""Tabular projection for the immutable graph core."""

from .errors import (
    MaterializationError,
    TableError,
)
from .table import Table

__all__ = [
    "MaterializationError",
    "Table",
    "TableError",
]
