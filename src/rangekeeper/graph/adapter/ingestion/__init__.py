"""Evidence foundation for deterministic, specification-driven adapters.

Includes numeric interpretation, selection and concatenation of table Evidence.
Source values are evidence, never executable instructions; source reading and
graph persistence remain separate concerns.
"""

from . import tabular
from .errors import EvidenceValidationError
from .evidence import Evidence, EvidenceKey, Issue, IssueSeverity
from .fingerprint import fingerprint
from .validation import validate

__all__ = [
    "Evidence",
    "EvidenceKey",
    "EvidenceValidationError",
    "Issue",
    "IssueSeverity",
    "fingerprint",
    "tabular",
    "validate",
]
