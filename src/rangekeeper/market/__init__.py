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
    from rangekeeper.market.view import Market as Market

_EXPORTS = {"Market": "view", "replay": "_replay", "ReplayUnavailableError": "_replay"}
_MODULES = {"dynamics", "generation"}
__all__ = ["dynamics", "generation", "Market", "replay", "ReplayUnavailableError"]
__getattr__, __dir__ = _lazy(__name__, names=_EXPORTS, modules=_MODULES)


"""Schema-generated path declarations and provenance records."""

from rangekeeper.schema.records import (
    CalculationProvenance,
    LibraryVersion,
    ObservationAvailability,
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
]
