from uuid import UUID


def is_text(value: object, *, empty: bool = True) -> bool:
    """Return whether a value is text, optionally excluding empty text."""
    return isinstance(value, str) and (empty or bool(value.strip()))


def require_uuid(value: object, field: str) -> UUID:
    """Return a UUID or raise a field-specific type error."""
    if not isinstance(value, UUID):
        raise TypeError(f"{field} must be a UUID")
    return value


def require_text(value: object, field: str) -> str:
    """Return non-empty text or raise a field-specific validation error."""
    if not is_text(value):
        raise TypeError(f"{field} must be a string")
    if not is_text(value, empty=False):
        raise ValueError(f"{field} must not be empty")
    return value


def optional_text(
    value: object,
    field: str,
    *,
    empty: bool = True,
) -> str | None:
    """Return optional text, optionally rejecting empty text."""
    if value is None:
        return None
    if not is_text(value):
        raise TypeError(f"{field} must be a string or None")
    if not empty and not is_text(value, empty=False):
        raise ValueError(f"{field} must not be empty")
    return value
