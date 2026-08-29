def is_text(value: object, *, empty: bool = True) -> bool:
    """Return whether a value is text, optionally excluding empty text."""
    return isinstance(value, str) and (empty or bool(value.strip()))
