"""Policy declarations and lazy finite evaluation over explicit observations."""

from typing import TYPE_CHECKING
from importlib import import_module

from rangekeeper.schema.records import (
    Action as Action,
    ActionKind as ActionKind,
    Decision as Decision,
    DecisionOutcome as DecisionOutcome,
    ObservationBinding as ObservationBinding,
    ObservedQuantity as ObservedQuantity,
    Policy as Policy,
    Rule as Rule,
)

if TYPE_CHECKING:
    from rangekeeper.specification.policy.evaluation import evaluate as evaluate
    from rangekeeper.specification.policy.observation import (
        observe as observe,
        PolicyCapabilityError as PolicyCapabilityError,
    )
    from rangekeeper.specification.policy.result import (
        Observation as Observation,
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
