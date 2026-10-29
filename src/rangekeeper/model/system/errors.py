"""Errors raised by Model selection, hierarchy building and value reduction."""

from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import RangekeeperError


class SelectionError(RangekeeperError, ValueError):
    """A Model selection or Value selector disagrees with its declared scope."""

    code = Code.SELECTION


class HierarchyError(RangekeeperError, ValueError):
    """A selected graph is not one rooted tree.

    ``code`` is a ``hierarchy.*`` code, given by keyword. ``targets`` are the
    Entities of the offending scope.
    """


class AggregationError(RangekeeperError, ValueError):
    """A recorded-quantity reduction cannot produce a meaningful finite result."""

    code = Code.AGGREGATION


__all__ = ["SelectionError", "HierarchyError", "AggregationError"]
