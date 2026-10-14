from collections.abc import Iterable
from uuid import UUID


class SelectionError(ValueError):
    """A Model selection or Value selector disagrees with its declared scope."""


class HierarchyError(ValueError):
    """A selected graph is not one rooted tree; IDs identify the offending scope."""

    def __init__(self, code: str, message: str, *, ids: Iterable[UUID] = ()) -> None:
        self.code = code
        self.ids = tuple(ids)
        super().__init__(f"{code}: {message}; ids={self.ids}")


class AggregationError(ValueError):
    """A recorded-quantity reduction cannot produce a meaningful finite result."""


__all__ = ["SelectionError", "HierarchyError", "AggregationError"]
