"""Policy declarations and lazy finite evaluation over explicit observations."""

from importlib import import_module
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


def __getattr__(name):
    if name not in _RUNTIME:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_RUNTIME[name]}"), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
