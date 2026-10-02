"""Writable revision-store contract; domain code depends only on its read protocols."""

from typing import Protocol, TypeAlias, TypeVar
from uuid import UUID

from ..model.model import Model
from ..specification.specification import Specification
from ..run.run import Run
from ..references import DocumentResolver

Document: TypeAlias = Model | Specification | Run
D = TypeVar("D", bound=Document)


class RecordStore(DocumentResolver, Protocol):
    """Append-only revisions, with idempotent identical writes and explicit conflicts."""

    def put(self, document: Document) -> UUID:
        """Validate and publish one revision; require referenced Run documents first."""
        ...
