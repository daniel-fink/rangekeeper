"""Market paths and the path generators that make them (ADR-014).

``Dynamics`` declares how one series moves, ``generate`` makes market paths
of named series, and ``Paths`` is the captured document. A path generator
satisfies ``PathGenerator`` and registers in ``generators``.
"""

from rangekeeper.market.generator import PathGenerator, generators
from rangekeeper.market.paths import MarketPath, Paths
from rangekeeper.market.series import Dynamics, DynamicsGenerator, generate
from rangekeeper.schema.records import (
    LibraryVersion,
    PathAmounts,
    PathCapture,
    PathParameter,
    PathSeries,
    RandomStream,
)

__all__ = [
    "Dynamics",
    "DynamicsGenerator",
    "generate",
    "Paths",
    "MarketPath",
    "PathGenerator",
    "generators",
    "LibraryVersion",
    "PathAmounts",
    "PathCapture",
    "PathParameter",
    "PathSeries",
    "RandomStream",
]
