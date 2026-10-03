"""Compatibility names for the shared graph boundary errors."""

from rangekeeper.errors import BoundaryError as AdapterError
from rangekeeper.errors import EncodingError as AdapterEncodingError

__all__ = ["AdapterEncodingError", "AdapterError"]
