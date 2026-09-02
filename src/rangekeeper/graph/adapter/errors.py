class AdapterError(Exception):
    """Base class for graph adapter failures."""


class AdapterEncodingError(AdapterError, ValueError):
    """Raised when an adapter cannot encode or decode its boundary format."""
