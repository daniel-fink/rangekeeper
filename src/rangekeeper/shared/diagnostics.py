"""Immutable diagnostics used by structural and bounded semantic validation."""

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
from uuid import UUID

from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, ValidationError


def frozen(entries: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Return a read-only copy of named diagnostic fields."""
    return MappingProxyType(dict(entries or {}))


@dataclass(frozen=True)
class Issue:
    """One validation finding: its code, message, document, path and fields.

    ``targets`` are the UUIDs of the records that the finding is about.
    ``values`` are the named inputs of the finding, for example the expected
    and actual kinds. ``evidence`` holds measured results, for example a
    residual. Read these fields, not the message.
    """

    code: Code
    message: str
    document_id: UUID | None = None
    path: str = ""
    targets: tuple[UUID, ...] = ()
    values: Mapping[str, Any] | None = field(default_factory=frozen, hash=False)
    evidence: Mapping[str, Any] | None = field(default_factory=frozen, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", Code(self.code))
        object.__setattr__(self, "targets", tuple(self.targets))
        object.__setattr__(self, "values", frozen(self.values))
        object.__setattr__(self, "evidence", frozen(self.evidence))

    @classmethod
    def from_error(
        cls,
        error: ContractError,
        *,
        document_id: UUID | None = None,
        prefix: str = "",
    ) -> "Issue":
        """Return the Issue of a ContractError, with a fallback document."""
        fields = error._fields()
        fields.update(
            code=error.code,
            document_id=error.document_id or document_id,
            path=prefix + error.path,
        )
        return cls(message=str(error), **fields)

    def replace(self, **changes: Any) -> "Issue":
        """Return a copy of this Issue with some fields changed."""
        return dataclasses.replace(self, **changes)

    def __reduce__(self) -> tuple[type["Issue"], tuple[Any, ...]]:
        # A read-only mapping does not pickle; its copy does.
        return type(self), (
            self.code,
            self.message,
            self.document_id,
            self.path,
            self.targets,
            dict(self.values or {}),
            dict(self.evidence or {}),
        )


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
