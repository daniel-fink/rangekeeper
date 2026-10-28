"""Lazy finite rule evaluation over explicit observations.

The declarations are in ``rangekeeper.specification.rule``.
"""

from rangekeeper.execution.rule.evaluation import evaluate
from rangekeeper.execution.rule.observation import RuleCapabilityError, observe
from rangekeeper.execution.rule.result import Observation, RuleResult

__all__ = [
    "evaluate",
    "observe",
    "RuleCapabilityError",
    "Observation",
    "RuleResult",
]
