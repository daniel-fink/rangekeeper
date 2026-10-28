"""Rule declarations and lazy finite evaluation over explicit observations."""

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
    ObservationBinding as ObservationBinding,
)
from rangekeeper.schema.records import (
    ObservedQuantity as ObservedQuantity,
)
from rangekeeper.schema.records import (
    Rule as Rule,
)
from rangekeeper.schema.records import RuleEvidence as RuleEvidence
from rangekeeper.schema.records import RuleSet as RuleSet
from rangekeeper.shared.exports import lazy as _lazy

if TYPE_CHECKING:
    from rangekeeper.specification.rule.evaluation import evaluate as evaluate
    from rangekeeper.specification.rule.observation import (
        RuleCapabilityError as RuleCapabilityError,
    )
    from rangekeeper.specification.rule.observation import observe as observe
    from rangekeeper.specification.rule.result import Observation as Observation
    from rangekeeper.specification.rule.result import RuleResult as RuleResult

_RUNTIME = {
    "evaluate": "evaluation",
    "observe": "observation",
    "RuleCapabilityError": "observation",
    "Observation": "result",
    "RuleResult": "result",
}
__all__ = [
    "Action",
    "ActionKind",
    "Decision",
    "RuleEvidence",
    "ObservationBinding",
    "ObservedQuantity",
    "RuleSet",
    "Rule",
    *_RUNTIME,
]


__getattr__, __dir__ = _lazy(__name__, names=_RUNTIME)
