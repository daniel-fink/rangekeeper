"""Model-backed graph operations with explicit remaining Graph retirement boundaries.

Presentation lives at rangekeeper.adapters and source building at rangekeeper.workflow.
Old domain classes, Graph JSON, Graph-only table projection and graph.legacy remain
for external consumer migration. No new constructor accepts both domain models.
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

_LEGACY_EXPORTS = {
    "Assembly": "assembly",
    "Characteristics": "characteristics",
    "Feature": "characteristics",
    "Label": "characteristics",
    "Measurement": "characteristics",
    "Classification": "classification",
    "Definitions": "definitions",
    "Entity": "entity",
    "Graph": "graph",
    "Relationship": "relationship",
    "Taxonomy": "taxonomy",
    **{
        name: "errors"
        for name in (
            "AmbiguousLookupError",
            "CatalogInstanceError",
            "GraphDependencyError",
            "GraphError",
            "IdentityConflictError",
            "InvalidAggregationError",
            "InvalidAssemblyError",
            "MissingEntityError",
            "MissingFactError",
            "MissingRelationshipError",
            "UnknownDefinitionError",
        )
    },
}
_MODULES = {
    "adapter",
    "provenance",
    "reduction",
    "revision",
    "table",
    "update",
    "projection",
    "membership",
    "selection",
    "reducers",
    "legacy",
}

__all__ = [
    "Assembly",
    "AmbiguousLookupError",
    "CatalogInstanceError",
    "Characteristics",
    "Classification",
    "Definitions",
    "Entity",
    "Feature",
    "Graph",
    "GraphDependencyError",
    "GraphError",
    "IdentityConflictError",
    "InvalidAggregationError",
    "InvalidAssemblyError",
    "Label",
    "Measurement",
    "MissingEntityError",
    "MissingFactError",
    "MissingRelationshipError",
    "Relationship",
    "Taxonomy",
    "UnknownDefinitionError",
    "View",
    "Hierarchy",
    "Reduction",
    "Aggregation",
    "Coverage",
    "SelectionError",
    "HierarchyError",
    "AggregationError",
    "projection",
    "membership",
    "selection",
    "reducers",
    "legacy",
    "adapter",
    "provenance",
    "reduction",
    "revision",
    "table",
    "update",
]


def __getattr__(name: str):
    if name in _MODULES:
        value = import_module(f"{__name__}.{name}")
    elif name in _LEGACY_EXPORTS:
        value = getattr(import_module(f"{__name__}.{_LEGACY_EXPORTS[name]}"), name)
    else:
        raise AttributeError(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
