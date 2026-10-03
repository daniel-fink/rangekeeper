"""Evidence foundation for deterministic, specification-driven adapters.

Includes numeric interpretation, selection and concatenation of table Evidence.
Source values are evidence, never executable instructions; source reading and
graph persistence remain separate concerns.
"""

from rangekeeper.workflow.ingestion import tabular
from rangekeeper.workflow.ingestion.errors import EvidenceValidationError
from rangekeeper.workflow.ingestion.evidence import (
    Evidence,
    EvidenceKey,
    Issue,
    IssueSeverity,
)
from rangekeeper.workflow.ingestion.fingerprint import fingerprint
from rangekeeper.workflow.ingestion.validation import validate

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
