"""Canonical Model envelopes; SDK transport is optional and explicit."""

from .mapping import decode_model, encode_model
from .errors import MappingError, TransportError

__all__ = ["decode_model", "encode_model", "MappingError", "TransportError"]
