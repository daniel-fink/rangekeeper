"""Graph views, traversal and reductions over canonical immutable Models.

Domain records belong to rangekeeper.model. The temporary Graph predecessor is
available only through rangekeeper.legacy.graph and is never imported here.
"""

from importlib import import_module
from .view import View as View
from .hierarchy import Hierarchy as Hierarchy
from .reduction import (
    Reduction as Reduction,
    Aggregation as Aggregation,
    Coverage as Coverage,
)
from .errors import (
    SelectionError as SelectionError,
    HierarchyError as HierarchyError,
    AggregationError as AggregationError,
)

_MODULES = {"reduction", "projection", "membership", "selection", "reducers"}
__all__ = [
    "View",
    "Hierarchy",
    "Reduction",
    "Aggregation",
    "Coverage",
    "SelectionError",
    "HierarchyError",
    "AggregationError",
    "reduction",
    "projection",
    "membership",
    "selection",
    "reducers",
]


def __getattr__(name: str):
    if name not in _MODULES:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
