"""Owner-local Value/Label access; Measure identity is not a unique Value key."""

from rangekeeper.schema.records import (
    Characteristics as Characteristics,
    Label as Label,
    Value as Value,
)
from rangekeeper.shared.arguments import require_text


def value(items: Characteristics | None, key: str) -> Value | None:
    """Find an exact case-sensitive Value key within one owner's Characteristics."""
    require_text(key, "key")
    return (
        next((item for item in (items.values or ()) if item.key == key), None)
        if items
        else None
    )


def label(items: Characteristics | None, key: str) -> Label | None:
    """Find an exact case-sensitive Label key; missing container/key returns None."""
    require_text(key, "key")
    return (
        next((item for item in (items.labels or ()) if item.key == key), None)
        if items
        else None
    )


__all__ = ["Characteristics", "Label", "Value", "value", "label"]

from rangekeeper.schema.enums import ValueKind

__all__ += ["ValueKind"]
