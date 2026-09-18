"""Structured request encoding; deliberately separate from Evidence payloads."""

from collections.abc import Mapping
from types import MappingProxyType

from .errors import AdapterEncodingError
from .ingestion._encoding import digest, encode
from .ingestion.errors import EvidenceValidationError


def freeze(value: object) -> object:
    """Copy structured parameters, preserving types and rejecting cyclic containers."""
    return _freeze(value, set())


def _freeze(value: object, active: set[int]) -> object:
    if isinstance(value, Mapping) or type(value) in (list, tuple):
        if id(value) in active:
            raise AdapterEncodingError("Cyclic specification")
        active.add(id(value))
        try:
            if isinstance(value, Mapping):
                if any(type(key) is not str for key in value):
                    raise AdapterEncodingError("Specification keys must be strings")
                return MappingProxyType({
                    k: _freeze(v, active) for k, v in value.items()
                })
            assert isinstance(value, (list, tuple))
            return tuple(_freeze(item, active) for item in value)
        finally:
            active.remove(id(value))
    try:
        encode(value)
    except EvidenceValidationError as exc:
        raise AdapterEncodingError(str(exc)) from exc
    return value


def freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("Expected a mapping")
    result = freeze(value)
    assert isinstance(result, Mapping)
    return result


def _encode_structure(value: object) -> object:
    """Encode already normalized structure using the existing scalar encoding."""
    if isinstance(value, Mapping):
        return ["mapping", [[k, _encode_structure(value[k])] for k in sorted(value)]]
    if type(value) is tuple:
        return ["sequence", [_encode_structure(item) for item in value]]
    return encode(value)


def fingerprint(value: object) -> str:
    return "sha256:" + digest(_encode_structure(freeze(value)))
