"""System records and lazy views over a complete pinned Model."""

from importlib import import_module
from typing import TYPE_CHECKING

from rangekeeper.schema.records import Assembly, Entity, Relationship, System

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
        Aggregation as Aggregation,
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
    "Aggregation": "reduction",
    "Coverage": "reduction",
    "CoverageStatus": "reduction",
    "classified": "reduction",
    "Pivot": "pivot",
    "PivotColumn": "pivot",
    "Partition": "pivot",
    "SelectionError": "errors",
    "HierarchyError": "errors",
    "AggregationError": "errors",
}
_MODULES = {"reduction", "projection", "membership", "selection", "reducers", "pivot"}
__all__ = ["System", "Entity", "Assembly", "Relationship", *_EXPORTS, *sorted(_MODULES)]


def __getattr__(name: str):
    if name in _EXPORTS:
        value = getattr(import_module(f".{_EXPORTS[name]}", __name__), name)
    elif name in _MODULES:
        value = import_module(f".{name}", __name__)
    else:
        raise AttributeError(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
