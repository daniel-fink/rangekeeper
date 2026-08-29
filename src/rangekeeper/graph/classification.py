from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from .. import validate


@dataclass(frozen=True, slots=True, kw_only=True)
class Classification:
    id: UUID = field(default_factory=uuid4)
    code: str
    name: str
    definition: str | None = None
    parent: Classification | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not validate.is_text(self.code):
            raise TypeError("Classification.code must be a string")
        if not validate.is_text(self.code, empty=False):
            raise ValueError("Classification.code must not be empty")
        if not validate.is_text(self.name):
            raise TypeError("Classification.name must be a string")
        if not validate.is_text(self.name, empty=False):
            raise ValueError("Classification.name must not be empty")
        if self.definition is not None and not isinstance(self.definition, str):
            raise TypeError("definition must be a string or None")
        if self.parent is not None and not isinstance(self.parent, Classification):
            raise TypeError("parent must be a Classification or None")

    def __str__(self) -> str:
        return self.name
