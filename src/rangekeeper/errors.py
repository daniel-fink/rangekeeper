"""The errors that Rangekeeper raises and the codes of its findings (ADR-016).

Every error subclasses ``RangekeeperError`` and has a ``code``. Read the code and
the error's fields, never its message: ``ErrorFields`` names the fields that
every error has. Most errors also subclass a built-in
type, for example ``ValidationError`` is a ``ValueError``. This module exports
the errors that several packages raise; an error of one package, such as
``rangekeeper.model.system.HierarchyError``, is exported by that package.
"""

from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    AttemptDeadlineError,
    BackendUnavailableError,
    ContractError,
    DecodeError,
    EncodingError,
    EquationError,
    ErrorFields,
    ExtensionConflictError,
    IdentityConflictError,
    MissingReferenceError,
    NumericalError,
    PublishedFileError,
    RangekeeperError,
    ReferenceTypeError,
    RevisionConflictError,
    TableError,
    UnitError,
    UnknownExtensionError,
    UnsupportedError,
    UnsupportedVersionError,
    ValidationError,
)

__all__ = [
    "AmbiguousReferenceError",
    "AttemptDeadlineError",
    "BackendUnavailableError",
    "Code",
    "ContractError",
    "DecodeError",
    "EncodingError",
    "EquationError",
    "ErrorFields",
    "ExtensionConflictError",
    "IdentityConflictError",
    "MissingReferenceError",
    "NumericalError",
    "PublishedFileError",
    "RangekeeperError",
    "ReferenceTypeError",
    "RevisionConflictError",
    "TableError",
    "UnitError",
    "UnknownExtensionError",
    "UnsupportedError",
    "UnsupportedVersionError",
    "ValidationError",
]
