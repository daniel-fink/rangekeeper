"""Writable revision-store contract; domain code depends only on its read protocols.

The protocol names the document facades for type checkers only, so this
lowest layer imports no higher layer at runtime (ADR-010).
"""

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from rangekeeper.shared.references import DocumentResolver

if TYPE_CHECKING:
    from rangekeeper.market.paths import Paths
    from rangekeeper.model.model import Model
    from rangekeeper.run.run import Run
    from rangekeeper.specification.specification import Specification


class RecordStore(DocumentResolver, Protocol):
    """Append-only revisions, with idempotent identical writes and explicit conflicts."""

    def put(self, document: "Model | Specification | Run | Paths") -> UUID:
        """Validate and publish one revision; require referenced Run documents first."""
        ...

    def load_paths(self, id: UUID) -> "Paths":
        """Return one market paths revision without drawing again."""
        ...

    def find_runs(self, *, specification: str) -> "tuple[Run, ...]":
        """Return the Runs of the Specifications named ``specification``.

        The Runs come in the order of their recorded finish times, earliest
        first, so ``[-1]`` is the Run that finished last. A batch Run takes
        the latest finish time of its cases. The result can be empty.
        """
        ...
