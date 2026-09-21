"""Compatibility names for the shared graph boundary errors."""

from rangekeeper.graph.errors import BoundaryError as AdapterError
from rangekeeper.graph.errors import EncodingError as AdapterEncodingError

__all__ = ["AdapterEncodingError", "AdapterError"]
