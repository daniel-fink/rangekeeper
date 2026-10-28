"""Decimal text and float64 conversion of currency amounts (ADR-023).

A currency amount is finite and has at most 15 significant digits. Its
canonical text has plain notation, no exponent, no sign for zero or positive
values, no leading zeros and no trailing fractional zeros. ``rangekeeper.money``
is the public module; the record runtime and the fingerprint encoding use these
functions directly.
"""

import math
import re
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation
from typing import cast

from rangekeeper.shared.errors import NumericalError

# float64 decimal precision (DBL_DIG): every valid amount converts to float64
# and back without change.
DIGITS = 15
PATTERN = re.compile(r"^(0|-?(0\.[0-9]*[1-9]|[1-9][0-9]*(\.[0-9]*[1-9])?))$")
# A decimal numeral in source text: no sign words, spaces, underscores or NaN.
_NUMERAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_CONTEXT = Context(prec=DIGITS, rounding=ROUND_HALF_EVEN)


def text(value: Decimal) -> str:
    """Return the canonical text of a finite Decimal, with any number of digits."""
    if not value.is_finite():
        raise ValueError(f"currency amount is not finite: {value}")
    result = format(value, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return "0" if result in ("-0", "0", "") else result


def digits(value: Decimal) -> int:
    """Return the significant digits of a finite Decimal, without trailing zeros."""
    numerals = "".join(map(str, value.as_tuple().digits)).strip("0")
    return len(numerals)


def parse(source: str) -> Decimal:
    """Read a decimal numeral exactly, never through float."""
    if not isinstance(source, str) or not _NUMERAL.fullmatch(source):
        raise ValueError(f"not a decimal numeral: {source!r}")
    return Decimal(source)


def canonical(source: str) -> str | None:
    """Return the canonical text of a decimal numeral, or None if it is not one."""
    if PATTERN.match(source):
        return source
    try:
        return text(parse(source))
    except (ValueError, InvalidOperation):
        return None


def text_digits(source: str) -> int:
    """Return the significant digits of canonical text, without a Decimal."""
    return len(source.replace("-", "").replace(".", "").strip("0"))


def float_text(number: float) -> str:
    """Return the canonical text of a finite float at 15 significant digits, half even."""
    return text(_CONTEXT.create_decimal(number))


def to_number(amount: Decimal) -> float:
    """Return the correctly rounded float64 of an amount for a calculation."""
    if type(amount) is not Decimal:
        raise TypeError("amount must be a Decimal")
    return float(amount)


def number(value: object) -> float:
    """Return a serialized magnitude as a number: canonical text becomes a float64.

    Other values are returned unchanged, so a check can still reject them.
    """
    if type(value) is str and PATTERN.match(value):
        return float(value)
    return cast(float, value)


def to_amount(number: float | int) -> Decimal:
    """Return the amount of a float64 result: 15 significant digits, half even.

    A value that is not finite raises NumericalError.
    """
    if type(number) is bool or type(number) not in (int, float):
        raise TypeError("number must be an int or a float")
    if type(number) is float and not math.isfinite(number):
        raise NumericalError(f"currency amount is not finite: {number}")
    return Decimal(
        float_text(number)
        if type(number) is float
        else text(_CONTEXT.create_decimal(number))
    )


__all__ = [
    "DIGITS",
    "PATTERN",
    "canonical",
    "digits",
    "float_text",
    "number",
    "parse",
    "text",
    "text_digits",
    "to_amount",
    "to_number",
]
