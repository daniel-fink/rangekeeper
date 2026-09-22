"""Evidence foundation for deterministic, specification-driven adapters.

Includes numeric interpretation, selection and concatenation of table Evidence.
Source values are evidence, never executable instructions; source reading and
graph persistence remain separate concerns.
"""

from rangekeeper.graph.workflow.ingestion import tabular
from rangekeeper.graph.workflow.ingestion.errors import EvidenceValidationError
from rangekeeper.graph.workflow.ingestion.evidence import (
    Evidence,
    EvidenceKey,
    Issue,
    IssueSeverity,
)
from rangekeeper.graph.workflow.ingestion.fingerprint import fingerprint
from rangekeeper.graph.workflow.ingestion.validation import validate

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
