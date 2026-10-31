"""The result of one check of a rule, which the rule engine and the trace check read.

LinkML defines it, in ``schema/rule.yaml``, because a stored ``Check`` records it.
"""

from rangekeeper.schema.enums import DecisionResult as DecisionResult

__all__ = ["DecisionResult"]
