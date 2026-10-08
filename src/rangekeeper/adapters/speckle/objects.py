"""SDK serialization ends here; mappings operate on detached transport data."""

import json
from collections.abc import Mapping
from rangekeeper.schema.runtime import _json_copy


def detach(value: object) -> dict:
    """Copy a mapping or serialize an SDK Base; never follow external references.

    The optional SDK is imported only for an SDK object. Unsupported objects,
    cycles, and non-JSON numbers fail rather than become lossy display strings.
    """
    if isinstance(value, Mapping):
        return _json_copy(value)
    from specklepy.api import operations
    from specklepy.objects import Base

    if not isinstance(value, Base):
        raise TypeError("expected a mapping or Speckle Base")
    result = json.loads(operations.serialize(value))
    return _json_copy(result)
