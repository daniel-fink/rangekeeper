"""Immutable Model, Specification and Run roots with explicit capability packages."""

from importlib import metadata as _metadata

from .model import Model
from .quantity import Quantity
from .run import Run
from .schema.runtime import OMIT
from .shared.exports import lazy as _lazy
from .specification import Specification

_LAZY_MODULES = frozenset(
    {
        "schema",
        "shared",
        "model",
        "specification",
        "run",
        "finance",
        "io",
        "duration",
        "errors",
        "execution",
        "expressions",
        "flow",
        "quantity",
        "money",
        "profile",
        "market",
    }
)
# Internal packages load on access but are not public (ADR-010).
_INTERNAL = frozenset({"schema", "shared"})
__all__ = [
    "Model",
    "Specification",
    "Run",
    "Quantity",
    "OMIT",
    "__version__",
    *sorted(_LAZY_MODULES - _INTERNAL),
]

try:
    __version__ = _metadata.version("rangekeeper")
except _metadata.PackageNotFoundError:  # A source tree that is not installed.
    __version__ = "0+unknown"

__getattr__, __dir__ = _lazy(__name__, modules=_LAZY_MODULES)
