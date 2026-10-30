"""Flows made from amounts in equations.

tools/expressions/generate.py writes this module from the equation-function
registry; do not edit it by hand.
"""

from rangekeeper.model.expression.terms import Operand, Term, call


def event(*, amount: Operand, on: Operand) -> Term:
    """Return a Flow with one amount, in the period that contains a date.

    ``amount``: The amount.
    ``on``: The date of the amount; NEVER gives zero in every period.

    Mirrors ``rangekeeper.flow.Flow``, with the amount on its date and zero
    elsewhere.
    """
    return call("rx.flow.event", amount=amount, on=on)


__all__ = [
    "event",
]
