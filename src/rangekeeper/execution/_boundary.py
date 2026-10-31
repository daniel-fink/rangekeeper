"""What crosses between a calling process and a batch worker process.

Records and facades are immutable and do not support ``pickle``: they hold
mapping proxies, and they refuse attribute writes. This module writes them as
their state, and it remakes each one with no further validation, because the
sender holds the same validated value. A Model keeps its index, because making
it again takes about ten times as long as reading it (ADR-013). A Specification
crosses without its Model, resolver, cases and Paths. These hold references
that may not move, such as a store, and no stage after composition reads them.

An encoded value is one line of ASCII text, so that it can use the JSON-line
``Worker`` of ``backends/_process.py``.
"""

import base64
import io
import pickle
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from rangekeeper.market.paths import Paths
from rangekeeper.model import Model
from rangekeeper.run import Run
from rangekeeper.schema.runtime import Record
from rangekeeper.specification import Composition, Specification


def _proxy(mapping: dict[Any, Any]) -> Mapping[Any, Any]:
    return MappingProxyType(mapping)


def _remake(cls: type, state: dict[str, Any]) -> Any:
    item: Any = object.__new__(cls)
    for name, value in state.items():
        object.__setattr__(item, name, value)
    return item


# Each kind that crosses, the attributes that it sends, and the attributes that
# it has on arrival without being sent.
_CROSSING: tuple[tuple[type, tuple[str, ...], dict[str, Any]], ...] = (
    (Record, ("_data",), {}),
    (Model, ("_record", "_index", "_keys", "_named", "_units", "_namespace"), {}),
    (
        Specification,
        ("_record",),
        {
            "_model": None,
            "_resolver": None,
            "_cases": MappingProxyType({}),
            "_paths": None,
        },
    ),
    (Run, ("_record",), {"_validated": None}),
    (Paths, ("_record",), {}),
    (Composition, ("requirements", "contributors", "sources"), {}),
)


class _Pickler(pickle.Pickler):
    """A pickler that writes mapping proxies, records and facades as above."""

    def reducer_override(self, obj: Any) -> Any:
        """Return how to remake a proxy, a record or a facade; or pickle as usual."""
        if isinstance(obj, MappingProxyType):
            return _proxy, (dict(obj),)
        for kind, names, fixed in _CROSSING:
            if isinstance(obj, kind):
                sent = {name: getattr(obj, name) for name in names}
                return _remake, (type(obj), {**sent, **fixed})
        return NotImplemented


def dumps(value: object) -> bytes:
    """Return the bytes of a value that may hold records and facades."""
    buffer = io.BytesIO()
    _Pickler(buffer, protocol=pickle.HIGHEST_PROTOCOL).dump(value)
    return buffer.getvalue()


def encode(value: object) -> str:
    """Return a value as one line of ASCII text."""
    return base64.b64encode(dumps(value)).decode("ascii")


def decode(line: str) -> Any:
    """Return the value of a line from ``encode``."""
    return pickle.loads(base64.b64decode(line))  # noqa: S301 - from our own child
