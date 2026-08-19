from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Provenance:
    source: str
    identifiers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.source = self._validate_text(self.source, "source")
        identifiers = dict(self.identifiers)
        for key, value in identifiers.items():
            self._validate_text(key, "identifier key")
            self._validate_text(value, f"identifier {key!r}")
        self.identifiers = identifiers

    @staticmethod
    def _validate_text(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string")
        if not value.strip():
            raise ValueError(f"{field} must not be empty")
        return value
