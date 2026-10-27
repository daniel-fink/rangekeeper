"""Market scenarios with lazy runtime imports and lightweight contract access."""

from typing import TYPE_CHECKING

from rangekeeper.shared.exports import lazy as _lazy

if TYPE_CHECKING:
    from rangekeeper.model.scenario import market as market
    from rangekeeper.model.scenario._replay import (
        ReplayUnavailableError as ReplayUnavailableError,
    )
    from rangekeeper.model.scenario._replay import replay as replay
    from rangekeeper.model.scenario.view import Market as Market

_EXPORTS = {"Market": "view", "replay": "_replay", "ReplayUnavailableError": "_replay"}
_MODULES = {"market"}
__all__ = ["market", "Market", "replay", "ReplayUnavailableError"]
__getattr__, __dir__ = _lazy(__name__, names=_EXPORTS, modules=_MODULES)


"""Schema-generated scenario declarations and provenance records."""

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
