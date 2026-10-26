"""Immutable diagnostics used by structural and bounded semantic validation."""

from dataclasses import dataclass
from uuid import UUID

from rangekeeper.shared.errors import ValidationError


@dataclass(frozen=True)
class Issue:
    """One validation finding with its code, message, document and path."""

    code: str
    message: str
    document_id: UUID | None = None
    path: str = ""


@dataclass(frozen=True)
class ValidationReport:
    """Ordered validation issues; an empty report is valid."""

    issues: tuple[Issue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))

    @property
    def valid(self) -> bool:
        """Return whether this report has no issues."""
        return not self.issues

    def raise_if_invalid(self) -> None:
        """Raise ValidationError when this report has issues."""
        if not self.valid:
            raise ValidationError(self)
