"""Errors raised by Model selection, hierarchy building and value reduction."""

from collections.abc import Iterable
from uuid import UUID

from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import RangekeeperError


class SelectionError(RangekeeperError, ValueError):
    """A Model selection or Value selector disagrees with its declared scope."""

    code = Code.SELECTION


class HierarchyError(RangekeeperError, ValueError):
    """A selected graph is not one rooted tree; IDs identify the offending scope."""

    def __init__(self, code: Code, message: str, *, ids: Iterable[UUID] = ()) -> None:
        self.code = Code(code)
        self.ids = tuple(ids)
        super().__init__(f"{message}; ids={self.ids}")


class AggregationError(RangekeeperError, ValueError):
    """A recorded-quantity reduction cannot produce a meaningful finite result."""

    code = Code.AGGREGATION


__all__ = ["SelectionError", "HierarchyError", "AggregationError"]
