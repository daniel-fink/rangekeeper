"""Policy declarations and lazy finite evaluation over explicit observations."""

from typing import TYPE_CHECKING

from rangekeeper.schema.records import (
    Action as Action,
)
from rangekeeper.schema.records import (
    ActionKind as ActionKind,
)
from rangekeeper.schema.records import (
    Decision as Decision,
)
from rangekeeper.schema.records import (
    DecisionOutcome as DecisionOutcome,
)
from rangekeeper.schema.records import (
    ObservationBinding as ObservationBinding,
)
from rangekeeper.schema.records import (
    ObservedQuantity as ObservedQuantity,
)
from rangekeeper.schema.records import (
    Policy as Policy,
)
from rangekeeper.schema.records import (
    Rule as Rule,
)
from rangekeeper.shared.exports import lazy as _lazy

if TYPE_CHECKING:
    from rangekeeper.specification.policy.evaluation import evaluate as evaluate
    from rangekeeper.specification.policy.observation import (
        PolicyCapabilityError as PolicyCapabilityError,
    )
    from rangekeeper.specification.policy.observation import (
        observe as observe,
    )
    from rangekeeper.specification.policy.result import (
        Observation as Observation,
    )
    from rangekeeper.specification.policy.result import (
        PolicyResult as PolicyResult,
    )

_RUNTIME = {
    "evaluate": "evaluation",
    "observe": "observation",
    "PolicyCapabilityError": "observation",
    "Observation": "result",
    "PolicyResult": "result",
}
__all__ = [
    "Action",
    "ActionKind",
    "Decision",
    "DecisionOutcome",
    "ObservationBinding",
    "ObservedQuantity",
    "Policy",
    "Rule",
    *_RUNTIME,
]


__getattr__, __dir__ = _lazy(__name__, names=_RUNTIME)
