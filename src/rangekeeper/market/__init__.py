"""Market paths and the path generators that make them (ADR-014).

``Dynamics`` declares how one series moves, ``generate`` makes market paths
of named series, and ``Paths`` is the captured document. The scenario plan,
``Market`` and ``replay`` load on first use; #140 removes them.
"""

from typing import TYPE_CHECKING

from rangekeeper.market.generator import PathGenerator, generators
from rangekeeper.market.paths import MarketPath, Paths
from rangekeeper.market.series import Dynamics, DynamicsGenerator, generate
from rangekeeper.shared.exports import lazy as _lazy

if TYPE_CHECKING:
    from rangekeeper.market._replay import (
        ReplayUnavailableError as ReplayUnavailableError,
    )
    from rangekeeper.market._replay import replay as replay
    from rangekeeper.market.view import Market as Market

_EXPORTS = {
    "Market": "view",
    "replay": "_replay",
    "ReplayUnavailableError": "_replay",
}
__all__ = [
    "Dynamics",
    "DynamicsGenerator",
    "generate",
    "Paths",
    "MarketPath",
    "PathGenerator",
    "generators",
    "Market",
    "replay",
    "ReplayUnavailableError",
]
__getattr__, __dir__ = _lazy(__name__, names=_EXPORTS)


"""Schema-generated path declarations and provenance records."""

from rangekeeper.schema.records import (
    CalculationProvenance,
    LibraryVersion,
    ObservationAvailability,
    PathAmounts,
    PathCapture,
    PathParameter,
    PathSeries,
    RandomStream,
    ScenarioParameter,
    ScenarioPlan,
    ScenarioRealization,
)

__all__ += [
    "ScenarioParameter",
    "ScenarioPlan",
    "ScenarioRealization",
    "CalculationProvenance",
    "RandomStream",
    "LibraryVersion",
    "ObservationAvailability",
    "PathAmounts",
    "PathCapture",
    "PathParameter",
    "PathSeries",
]
