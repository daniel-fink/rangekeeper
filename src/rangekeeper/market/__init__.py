"""Market path generators, captured paths and replay, with lazy runtime imports."""

from typing import TYPE_CHECKING

from rangekeeper.shared.exports import lazy as _lazy

if TYPE_CHECKING:
    from rangekeeper.market import dynamics as dynamics
    from rangekeeper.market import generation as generation
    from rangekeeper.market._replay import (
        ReplayUnavailableError as ReplayUnavailableError,
    )
    from rangekeeper.market._replay import replay as replay
    from rangekeeper.market.generator import PathGenerator as PathGenerator
    from rangekeeper.market.generator import generators as generators
    from rangekeeper.market.paths import MarketPath as MarketPath
    from rangekeeper.market.paths import Paths as Paths
    from rangekeeper.market.view import Market as Market

_EXPORTS = {
    "Market": "view",
    "replay": "_replay",
    "ReplayUnavailableError": "_replay",
    "Paths": "paths",
    "MarketPath": "paths",
    "PathGenerator": "generator",
    "generators": "generator",
}
_MODULES = {"dynamics", "generation"}
__all__ = [
    "dynamics",
    "generation",
    "Market",
    "replay",
    "ReplayUnavailableError",
    "Paths",
    "MarketPath",
    "PathGenerator",
    "generators",
]
__getattr__, __dir__ = _lazy(__name__, names=_EXPORTS, modules=_MODULES)


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
