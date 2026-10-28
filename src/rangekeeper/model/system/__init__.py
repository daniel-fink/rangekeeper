"""Lazy views over a complete pinned Model; `rangekeeper.model` exports the System records."""

from typing import TYPE_CHECKING

from rangekeeper.shared.exports import lazy as _lazy

if TYPE_CHECKING:
    from .errors import (
        AggregationError as AggregationError,
    )
    from .errors import (
        HierarchyError as HierarchyError,
    )
    from .errors import (
        SelectionError as SelectionError,
    )
    from .hierarchy import Hierarchy as Hierarchy
    from .hierarchy import HierarchyKind as HierarchyKind
    from .matching import Match as Match
    from .pivot import (
        Partition as Partition,
    )
    from .pivot import (
        Pivot as Pivot,
    )
    from .pivot import (
        PivotColumn as PivotColumn,
    )
    from .reduction import (
        Contributor as Contributor,
    )
    from .reduction import (
        Coverage as Coverage,
    )
    from .reduction import (
        CoverageStatus as CoverageStatus,
    )
    from .reduction import (
        Reduction as Reduction,
    )
    from .reduction import RollupResult as RollupResult
    from .reduction import (
        classified as classified,
    )
    from .view import View as View

_EXPORTS = {
    "View": "view",
    "Hierarchy": "hierarchy",
    "HierarchyKind": "hierarchy",
    "Reduction": "reduction",
    "Contributor": "reduction",
    "RollupResult": "reduction",
    "Coverage": "reduction",
    "CoverageStatus": "reduction",
    "classified": "reduction",
    "Match": "matching",
    "Pivot": "pivot",
    "PivotColumn": "pivot",
    "Partition": "pivot",
    "SelectionError": "errors",
    "HierarchyError": "errors",
    "AggregationError": "errors",
}
_MODULES = {
    "matching",
    "reduction",
    "table",
    "membership",
    "selection",
    "reducers",
    "pivot",
}
__all__ = [*_EXPORTS, *sorted(_MODULES)]


__getattr__, __dir__ = _lazy(__name__, names=_EXPORTS, modules=_MODULES)
