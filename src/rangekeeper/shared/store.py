"""Writable revision-store contract; domain code depends only on its read protocols.

The protocol names the three document facades for type checkers only, so this
lowest layer imports no higher layer at runtime (ADR-010).
"""

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from rangekeeper.shared.references import DocumentResolver

if TYPE_CHECKING:
    from rangekeeper.model.model import Model
    from rangekeeper.run.run import Run
    from rangekeeper.specification.specification import Specification


class RecordStore(DocumentResolver, Protocol):
    """Append-only revisions, with idempotent identical writes and explicit conflicts."""

    def put(self, document: "Model | Specification | Run") -> UUID:
        """Validate and publish one revision; require referenced Run documents first."""
        ...
