"""Small Python argument guards, separate from document semantic validation."""

from typing import TypeGuard
from uuid import UUID

from rangekeeper.shared.errors import ContractError


def is_text(value: object, *, empty: bool = True) -> TypeGuard[str]:
    """Return whether a value is text, optionally excluding empty text."""
    return isinstance(value, str) and (empty or bool(value.strip()))


def require_uuid(value: object, field: str) -> UUID:
    """Return a UUID or raise a field-specific type error."""
    if not isinstance(value, UUID):
        raise TypeError(f"{field} must be a UUID")
    return value


def _empty(field: str) -> ContractError:
    """Return the error for empty text in a field."""
    return ContractError(f"{field} must not be empty", values={"field": field})


def require_text(value: object, field: str) -> str:
    """Return non-empty text; raise TypeError or ContractError for the field."""
    if not is_text(value):
        raise TypeError(f"{field} must be a string")
    if not is_text(value, empty=False):
        raise _empty(field)
    return value


def require_code(value: object, field: str) -> str:
    """Validate a case-sensitive code without silently normalizing it."""
    result = require_text(value, field)
    if result != result.strip():
        raise ContractError(
            f"{field} must not have leading or trailing whitespace",
            values={"field": field, "value": result},
        )
    return result


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
        raise _empty(field)
    return value
