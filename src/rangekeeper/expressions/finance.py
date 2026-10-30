"""Valuation and interest in equations, on one date basis.

tools/expressions/generate.py writes this module from the equation-function
registry; do not edit it by hand.
"""

from rangekeeper.model.expression.terms import Operand, Term, call


def interest(*, balance: Operand, rate: Operand) -> Term:
    """Return the interest on a balance in each period.

    ``balance``: The balance of each period.
    ``rate``: An effective rate per year, such as 7 % pa.

    Mirrors ``rangekeeper.finance.interest``.
    """
    return call("rx.finance.interest", balance=balance, rate=rate)


def irr(*, flow: Operand) -> Term:
    """Return the internal rate of return of a Flow: the rate whose NPV is zero.

    ``flow``: The cash flow, with both signs.

    Mirrors ``rangekeeper.finance.irr``.
    """
    return call("rx.finance.irr", flow=flow)


def npv(*, flow: Operand, rate: Operand, on: Operand) -> Term:
    """Return the net present value of a Flow on a date.

    ``flow``: The cash flow.
    ``rate``: An effective rate per year, such as 7 % pa.
    ``on``: The date of the value.

    Mirrors ``rangekeeper.finance.npv``.
    """
    return call("rx.finance.npv", flow=flow, rate=rate, on=on)


__all__ = [
    "interest",
    "irr",
    "npv",
]
