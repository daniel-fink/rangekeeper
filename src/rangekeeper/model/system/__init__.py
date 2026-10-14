"""System records and lazy views over a complete pinned Model."""

from importlib import import_module
from typing import TYPE_CHECKING
from rangekeeper.schema.records import System, Entity, Assembly, Relationship

if TYPE_CHECKING:
    from .view import View as View
    from .hierarchy import Hierarchy as Hierarchy, HierarchyKind as HierarchyKind
    from .reduction import (
        Reduction as Reduction,
        Contributor as Contributor,
        Aggregation as Aggregation,
        Coverage as Coverage,
        CoverageStatus as CoverageStatus,
    )
    from .errors import (
        SelectionError as SelectionError,
        HierarchyError as HierarchyError,
        AggregationError as AggregationError,
    )

_EXPORTS = {
    "View": "view",
    "Hierarchy": "hierarchy",
    "HierarchyKind": "hierarchy",
    "Reduction": "reduction",
    "Contributor": "reduction",
    "Aggregation": "reduction",
    "Coverage": "reduction",
    "CoverageStatus": "reduction",
    "SelectionError": "errors",
    "HierarchyError": "errors",
    "AggregationError": "errors",
}
_MODULES = {"reduction", "projection", "membership", "selection", "reducers"}
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
