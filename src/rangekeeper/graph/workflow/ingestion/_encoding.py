"""Evidence-specific error translation around shared canonical scalar encoding."""

from rangekeeper.graph._encoding import canonical_json, digest
from rangekeeper.graph._encoding import encode as _encode
from rangekeeper.graph.errors import ValueEncodingError

from .errors import EvidenceValidationError

__all__ = ["canonical_json", "digest", "encode"]


def encode(value: object) -> object:
    try:
        return _encode(value)
    except ValueEncodingError as exc:
        raise EvidenceValidationError(exc.code, exc.message) from exc
