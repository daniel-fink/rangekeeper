"""Strict immutable payloads and version-independent canonical primitives."""

import json
import math
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from uuid import UUID
from zoneinfo import ZoneInfo

from .errors import EvidenceValidationError


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def digest(value: object) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def encode(value: object) -> object:
    """Encode supported immutable values with exact, type-sensitive semantics.

    This is a fingerprint encoding, not a general persistence or export format.
    Exact types exclude mutable subclasses. Mappings belong to container structure,
    not value payloads; structured source payloads can use tuples of named values.
    """
    kind = type(value)
    if value is None:
        return ["none"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", str(value)]
    if type(value) is float:
        if not math.isfinite(value):
            raise EvidenceValidationError("unsupported_value", "Non-finite float")
        return ["float", value.hex()]
    if type(value) is str:
        return ["str", value]
    if type(value) is UUID:
        return ["uuid", value.hex]
    if isinstance(value, (datetime, time)) and kind in (datetime, time):
        if value.tzinfo is not None and type(value.tzinfo) not in (timezone, ZoneInfo):
            raise EvidenceValidationError(
                "unsupported_value", "Mutable/custom timezone"
            )
        zone = value.tzinfo.key if isinstance(value.tzinfo, ZoneInfo) else None
        return [kind.__name__, value.isoformat(), value.fold, zone]
    if type(value) is date:
        return ["date", value.isoformat()]
    if type(value) is timedelta:
        return ["timedelta", value.days, value.seconds, value.microseconds]
    if type(value) is tuple:
        return ["tuple", [encode(item) for item in value]]
    if type(value) is frozenset:
        return [
            "frozenset",
            sorted((encode(item) for item in value), key=canonical_json),
        ]
    raise EvidenceValidationError(
        "unsupported_value", f"Expected immutable supported value, got {kind.__name__}"
    )
