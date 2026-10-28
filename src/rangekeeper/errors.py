"""The errors that Rangekeeper raises and the codes of its findings (ADR-016).

Every error subclasses ``RangekeeperError`` and has a ``code``. Read the code and
the error's fields, never its message. Most errors also subclass a built-in
type, for example ``ValidationError`` is a ``ValueError``. This module exports
the errors that several packages raise; an error of one package, such as
``rangekeeper.model.system.HierarchyError``, is exported by that package.
"""

from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AttemptDeadlineError,
    BackendUnavailableError,
    ContractError,
    DecodeError,
    EncodingError,
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
    "AttemptDeadlineError",
    "BackendUnavailableError",
    "Code",
    "ContractError",
    "DecodeError",
    "EncodingError",
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
