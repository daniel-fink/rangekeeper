"""Canonical Model envelopes; SDK transport is optional and explicit."""

from rangekeeper.adapters.speckle.mapping import decode_model, encode_model
from rangekeeper.adapters.speckle.errors import MappingError, TransportError

__all__ = ["decode_model", "encode_model", "MappingError", "TransportError"]
