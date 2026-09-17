"""Failures of the Evidence contract, distinct from source-data issues."""

from ..errors import AdapterError


class EvidenceValidationError(AdapterError, ValueError):
    """An invalid snapshot, address or evidence association."""

    def __init__(
        self, code: str, message: str, *, key: tuple[str, ...] | None = None
    ) -> None:
        self.code = code
        self.key = key
        super().__init__(
            f"{code}: {message}" + (f" at {key!r}" if key is not None else "")
        )
