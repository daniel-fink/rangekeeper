"""Retained immutable Graph predecessor and its own views and persistence."""

from importlib import import_module

_EXPORTS = {
    "View": "view",
    "Reduction": "reduction",
    "Aggregation": "reduction",
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
    "Reduction",
    "Aggregation",
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
    elif name in _EXPORTS:
        value = getattr(import_module(f"{__name__}.{_EXPORTS[name]}"), name)
    else:
        raise AttributeError(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
