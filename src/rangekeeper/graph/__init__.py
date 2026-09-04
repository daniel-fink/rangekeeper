from importlib import import_module
from types import ModuleType

from . import provenance as provenance
from . import reduction as reduction
from . import revision as revision
from . import table as table
from . import update as update
from .assembly import Assembly
from .characteristics import Characteristics, Feature, Label, Measurement
from .classification import Classification
from .definitions import Definitions
from .entity import Entity
from .errors import (
    AmbiguousLookupError,
    CatalogInstanceError,
    GraphDependencyError,
    GraphError,
    IdentityConflictError,
    InvalidAggregationError,
    InvalidAssemblyError,
    MissingEntityError,
    MissingFactError,
    MissingRelationshipError,
    UnknownDefinitionError,
)
from .graph import Graph
from .relationship import Relationship
from .taxonomy import Taxonomy
from .view import View


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
    "adapter",
    "provenance",
    "reduction",
    "revision",
    "table",
    "update",
]


def __getattr__(name: str) -> ModuleType:
    if name != "adapter":
        raise AttributeError(name)
    module = import_module(f"{__name__}.adapter")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted({*globals(), "adapter"})
