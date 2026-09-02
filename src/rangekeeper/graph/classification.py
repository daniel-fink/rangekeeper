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
        validate.require_uuid(self.id, "id")
        validate.require_text(self.code, "Classification.code")
        validate.require_text(self.name, "Classification.name")
        validate.optional_text(self.definition, "definition")
        if self.parent is not None and not isinstance(self.parent, Classification):
            raise TypeError("parent must be a Classification or None")

    def __str__(self) -> str:
        return self.name
