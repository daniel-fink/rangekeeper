"""The Python form of equations, imported as ``rx`` (D32).

``import rangekeeper.expressions as rx``. A declaration on an entity handle
returns a value handle, and ``project.ref(key=)`` finds one; operators on
handles and Terms build equations, such as ``noi == coverage * debt_service``,
and ``project.equations(...)`` adds them. The functions have the names of
equation text: ``rx.max(a, b)`` here, and ``rx.profile``, ``rx.flow`` and
``rx.finance``. ``rk.`` computes on values now; ``rx.`` builds an equation.
Text and ``rx`` make the same records.

``max`` and ``min`` keep the names of Python's built-ins, as in equation text (D21).

tools/expressions/generate.py writes this module from the equation-function
registry; do not edit it by hand.
"""

from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.functions import (
    Availability,
    EquationFunction,
    EvaluationStage,
    Form,
    FunctionParameter,
)
from rangekeeper.model.expression.terms import Operand, Term, call

from . import finance, flow, profile


def max(left: Operand, right: Operand) -> Term:
    """Return the larger of two values, period by period for Flows.

    ``left``: A value or a Flow.
    ``right``: A value or a Flow, in units compatible with left.

    Mirrors Python's built-in max, period by period.
    """
    return call("rx.max", left, right)


def min(left: Operand, right: Operand) -> Term:
    """Return the smaller of two values, period by period for Flows.

    ``left``: A value or a Flow.
    ``right``: A value or a Flow, in units compatible with left.

    Mirrors Python's built-in min, period by period.
    """
    return call("rx.min", left, right)


__all__ = [
    "max",
    "min",
    "Availability",
    "EquationFunction",
    "EvaluationStage",
    "Form",
    "FunctionParameter",
    "Operand",
    "Term",
    "functions",
    "finance",
    "flow",
    "profile",
]
