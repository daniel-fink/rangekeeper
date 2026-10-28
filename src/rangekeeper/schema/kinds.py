"""The kind registry: the owner class that each schema kind decodes to.

Generated records contain data only. An owner package adds behaviour with a
subclass, for example ``class Flow(records.Flow)`` in ``flow``, and registers
it here. Construction, ``from_data``, child access and traversal then return
the owner class. The generated ``_OWNERS`` table names the module of each
owner, so a decode loads the owner on first use without a static upward import.
"""

from __future__ import annotations

import sys
from importlib import import_module
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from rangekeeper.schema.runtime import Record

R = TypeVar("R", bound="type[Record]")
_REGISTERED: dict[str, type[Record]] = {}
# Resolved classes, including generated records with no owner.
_RESOLVED: dict[str, type[Record]] = {}


def register(cls: R) -> R:
    """Register an owner subclass for its kind and return it unchanged.

    The class must subclass the generated record of its kind directly, keep
    ``__slots__ = ()``, keep the generated constructor and not shadow a field.
    """
    from rangekeeper.schema.records import _OWNERS, _TYPES
    from rangekeeper.schema.validation import _slot_map

    kind = cls._kind
    generated = _TYPES.get(kind)
    if generated is None or generated not in cls.__bases__:
        raise TypeError(f"{cls.__name__} must subclass the generated {kind} record")
    owner = _OWNERS.get(kind)
    if owner is None or not (cls.__module__ + ".").startswith(owner + "."):
        raise TypeError(f"{kind} is owned by {owner}, not {cls.__module__}")
    if cls.__dict__.get("__slots__") != ():
        raise TypeError(f"{cls.__name__} must declare __slots__ = ()")
    if "__init__" in cls.__dict__ or "__new__" in cls.__dict__:
        raise TypeError(f"{cls.__name__} must keep the generated constructor")
    shadowed = sorted(set(_slot_map(kind)) & set(cls.__dict__))
    if shadowed:
        raise TypeError(f"{cls.__name__} shadows fields: {', '.join(shadowed)}")
    previous = _REGISTERED.get(kind)
    if previous is not None and previous is not cls:
        raise TypeError(f"{kind} is already registered to {previous.__qualname__}")
    _REGISTERED[kind] = _RESOLVED[kind] = cls
    # Bind the name that generated annotations use, so get_type_hints works.
    setattr(sys.modules["rangekeeper.schema.records"], f"_{kind}", cls)
    return cls


def record_type(kind: str) -> type[Record]:
    """Return the class that records of ``kind`` construct and decode to.

    The owner module loads on first use. While that module is still importing,
    the generated record is returned.
    """
    resolved = _RESOLVED.get(kind)
    if resolved is not None:
        return resolved
    from rangekeeper.schema.records import _OWNERS, _TYPES

    module = _OWNERS.get(kind)
    if module is None:
        _RESOLVED[kind] = _TYPES[kind]
        return _TYPES[kind]
    import_module(module)
    return _REGISTERED.get(kind, _TYPES[kind])
