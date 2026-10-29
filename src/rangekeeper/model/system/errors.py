"""Errors raised by Model selection, hierarchy building and rollups."""

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


class RollupError(RangekeeperError, ValueError):
    """A rollup or pivot cannot produce a meaningful finite result.

    ``rollup`` is the word for totals over a hierarchy; ``aggregate`` is the
    word for combining Flows (D38).
    """

    code = Code.ROLLUP


__all__ = ["SelectionError", "HierarchyError", "RollupError"]
