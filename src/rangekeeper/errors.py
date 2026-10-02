"""Errors shared by the schema-derived record boundary."""


class ContractError(ValueError):
    """A semantic rule failed, optionally identifying its code and JSON Pointer.

    The message remains the exception text. Validation entrypoints retain the
    structured context when converting this failure into a diagnostic report.
    """

    def __init__(
        self, message: str, *, code: str = "semantic.contract", path: str = ""
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


class ValidationError(ValueError):
    """A document or record failed validation; ``report`` retains diagnostics."""

    def __init__(self, report):
        self.report = report
        super().__init__(
            "; ".join(
                f"{issue.path or '/'}: {issue.message}" for issue in report.issues
            )
        )


class UnsupportedVersionError(ValueError):
    """A document uses a schema version unsupported by this installed library."""


class MissingReferenceError(LookupError):
    """A UUID does not exist in the requested document or resolver scope."""


class ReferenceTypeError(TypeError):
    """A resolved UUID names a different kind of record than the caller requested."""


class IdentityConflictError(ValueError):
    """One identity is declared more than once or resolves to conflicting content."""


class RevisionConflictError(ValueError):
    """A revision request conflicts with identity, lineage, or revision content."""


class UnitError(ValueError):
    """Units are unknown, malformed, incompatible, or produce a non-finite result."""


class DecodeError(ValueError):
    """Interchange text or a storage envelope cannot be decoded unambiguously."""
