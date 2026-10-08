"""Immutable diagnostics used by structural and bounded semantic validation."""

from dataclasses import dataclass
from uuid import UUID

from rangekeeper.shared.errors import ValidationError


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    document_id: UUID | None = None
    path: str = ""


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[Issue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))

    @property
    def valid(self) -> bool:
        return not self.issues

    def raise_if_invalid(self) -> None:
        if not self.valid:
            raise ValidationError(self)
