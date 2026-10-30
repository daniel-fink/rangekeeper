"""Profiles in equations: a Flow made by a growth or a distribution profile.

tools/expressions/generate.py writes this module from the equation-function
registry; do not edit it by hand.
"""

from collections.abc import Callable

from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.terms import Operand, Term, call, given
from rangekeeper.shared.errors import ContractError


def compounding(
    *,
    initial: Operand,
    rate: Operand,
    start: Operand | None = None,
    every: Operand | None = None,
    base: Operand | None = None,
) -> Term:
    """Return a Flow made by the growth profile Compounding.

    ``initial``: The amount of the first period, or on base.
    ``rate``: The growth rate per year, such as 2 % pa.
    ``start``: The date from which the profile has amounts; NEVER gives zero in
    every period.
    ``every``: A length, such as 5 years: an amount on start and once each
    length after it.
    ``base``: The date of the initial amount; by default the start of the first
    period.

    Mirrors ``rangekeeper.flow.Flow.from_profile`` with
    ``rangekeeper.profile.Compounding``.
    """
    return call(
        "rx.profile.compounding",
        initial=initial,
        rate=rate,
        **given(start=start, every=every, base=base),
    )


def constant(
    *, initial: Operand, start: Operand | None = None, every: Operand | None = None
) -> Term:
    """Return a Flow made by the growth profile Constant.

    ``initial``: The amount of the first period, or on base.
    ``start``: The date from which the profile has amounts; NEVER gives zero in
    every period.
    ``every``: A length, such as 5 years: an amount on start and once each
    length after it.

    Mirrors ``rangekeeper.flow.Flow.from_profile`` with
    ``rangekeeper.profile.Constant``.
    """
    return call(
        "rx.profile.constant", initial=initial, **given(start=start, every=every)
    )


def linear(
    *,
    initial: Operand,
    rate: Operand,
    start: Operand | None = None,
    every: Operand | None = None,
    base: Operand | None = None,
) -> Term:
    """Return a Flow made by the growth profile Linear.

    ``initial``: The amount of the first period, or on base.
    ``rate``: The growth rate per year, such as 2 % pa.
    ``start``: The date from which the profile has amounts; NEVER gives zero in
    every period.
    ``every``: A length, such as 5 years: an amount on start and once each
    length after it.
    ``base``: The date of the initial amount; by default the start of the first
    period.

    Mirrors ``rangekeeper.flow.Flow.from_profile`` with
    ``rangekeeper.profile.Linear``.
    """
    return call(
        "rx.profile.linear",
        initial=initial,
        rate=rate,
        **given(start=start, every=every, base=base),
    )


def scurve(
    *, total: Operand, start: Operand | None = None, length: Operand | None = None
) -> Term:
    """Return a Flow made by the distribution profile SCurve.

    ``total``: The total that the profile divides over the periods.
    ``start``: The date from which the profile has amounts; NEVER gives zero in
    every period.
    ``length``: The length of time over which the total is divided, such as 2
    years.

    Mirrors ``rangekeeper.flow.Flow.from_profile`` with
    ``rangekeeper.profile.SCurve``.
    """
    return call("rx.profile.scurve", total=total, **given(start=start, length=length))


def uniform(
    *, total: Operand, start: Operand | None = None, length: Operand | None = None
) -> Term:
    """Return a Flow made by the distribution profile Uniform.

    ``total``: The total that the profile divides over the periods.
    ``start``: The date from which the profile has amounts; NEVER gives zero in
    every period.
    ``length``: The length of time over which the total is divided, such as 2
    years.

    Mirrors ``rangekeeper.flow.Flow.from_profile`` with
    ``rangekeeper.profile.Uniform``.
    """
    return call("rx.profile.uniform", total=total, **given(start=start, length=length))


def __getattr__(name: str) -> Callable[..., Term]:
    """Return the equation function of a profile that an extension registers.

    A profile in ``rangekeeper.profile.profiles`` is an equation function under
    its name (D12). Its arguments are its amount and its options, by name.
    """
    try:
        function = functions.function(name=f"profile.{name}")
    except ContractError as error:
        raise AttributeError(name) from error

    def build(**arguments: Operand) -> Term:
        return call(function.code, **arguments)

    build.__name__ = name
    build.__doc__ = function.summary
    return build


__all__ = [
    "compounding",
    "constant",
    "linear",
    "scurve",
    "uniform",
]
