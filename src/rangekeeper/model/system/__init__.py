"""Lazy views over a complete pinned Model; `rangekeeper.model` exports the System records."""

from typing import TYPE_CHECKING

from rangekeeper.shared.exports import lazy as _lazy

if TYPE_CHECKING:
    from .errors import (
        HierarchyError as HierarchyError,
    )
    from .errors import (
        RollupError as RollupError,
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
    from .rollup import Contributor as Contributor
    from .rollup import Coverage as Coverage
    from .rollup import CoverageStatus as CoverageStatus
    from .rollup import FlowRollup as FlowRollup
    from .rollup import QuantityRollup as QuantityRollup
    from .rollup import Reducer as Reducer
    from .rollup import RollupEntry as RollupEntry
    from .rollup import RollupResult as RollupResult
    from .rollup import classified as classified
    from .view import View as View

_EXPORTS = {
    "View": "view",
    "Hierarchy": "hierarchy",
    "HierarchyKind": "hierarchy",
    "QuantityRollup": "rollup",
    "FlowRollup": "rollup",
    "Reducer": "rollup",
    "Contributor": "rollup",
    "RollupResult": "rollup",
    "RollupEntry": "rollup",
    "Coverage": "rollup",
    "CoverageStatus": "rollup",
    "classified": "rollup",
    "Match": "matching",
    "Pivot": "pivot",
    "PivotColumn": "pivot",
    "Partition": "pivot",
    "SelectionError": "errors",
    "HierarchyError": "errors",
    "RollupError": "errors",
}
_MODULES = {
    "matching",
    "rollup",
    "table",
    "membership",
    "selection",
    "pivot",
}
__all__ = [*_EXPORTS, *sorted(_MODULES)]


__getattr__, __dir__ = _lazy(__name__, names=_EXPORTS, modules=_MODULES)
