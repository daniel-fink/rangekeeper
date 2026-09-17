"""Evidence foundation for deterministic, specification-driven adapters.

No source-reading, interpretation, workflow-service or graph-persistence API is
provided here yet. Source values are evidence, never executable instructions.
"""

from . import tabular
from .errors import EvidenceValidationError
from .evidence import Evidence, EvidenceKey, Issue, IssueSeverity, fingerprint, validate

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
