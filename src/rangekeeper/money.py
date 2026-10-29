"""Currency amounts: the ISO 4217 catalogue, boundary conversions and rounding.

A currency amount is a magnitude whose units are exactly one ISO 4217 code,
for example ``AUD`` (ADR-023). Records hold it as a ``Decimal`` with at most 15
significant digits. Calculations use float64: ``to_number`` converts an amount
for a calculation, and ``to_amount`` converts a float64 result back. The
library rounds to minor units only on request, with ``round``.
"""

import math
from decimal import (
    ROUND_05UP,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Context,
    Decimal,
)
from enum import StrEnum, unique

from moneyed import list_all_currencies

from rangekeeper.shared.amounts import (
    DIGITS,
    encoded,
    text,
    text_digits,
    to_amount,
    to_number,
)
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, UnitError

CURRENCIES = tuple(currency.code for currency in list_all_currencies())
# The version of the numerical convention that each Run records as the
# Implementation ``rangekeeper.money`` (ADR-023): float64 inside, math.fsum for
# sums, to_number correctly rounded and to_amount at 15 significant digits,
# half even. A change to one of these rules needs a new version.
CONVENTION = "1"

# ISO 4217 lists no minor unit ("N.A.") for these codes; py-moneyed gives 1.
_NO_MINOR_UNIT = frozenset(
    {
        "XAG",
        "XAU",
        "XBA",
        "XBB",
        "XBC",
        "XBD",
        "XDR",
        "XPD",
        "XPT",
        "XSU",
        "XTS",
        "XUA",
        "XXX",
    }
)
_MINOR_UNITS: dict[str, int | None] = {
    currency.code: (
        None
        if currency.code in _NO_MINOR_UNIT
        else int(math.log10(currency.sub_unit) + 0.5)
    )
    for currency in list_all_currencies()
}
_CODES = frozenset(CURRENCIES)


@unique
class RoundingMode(StrEnum):
    """Select how ``round`` treats the dropped digits of an amount.

    Each member is the rounding constant of the ``decimal`` module with the
    same name, so ``RoundingMode.HALF_UP == decimal.ROUND_HALF_UP``.
    """

    HALF_EVEN = ROUND_HALF_EVEN
    HALF_UP = ROUND_HALF_UP
    HALF_DOWN = ROUND_HALF_DOWN
    UP = ROUND_UP
    DOWN = ROUND_DOWN
    CEILING = ROUND_CEILING
    FLOOR = ROUND_FLOOR
    ZERO_FIVE_UP = ROUND_05UP


MODES = frozenset(RoundingMode)


def is_currency(units: str) -> bool:
    """Return whether units text is exactly one ISO 4217 code, such as ``AUD``.

    Rates such as ``AUD/m^2`` and ``AUD/year`` are not currencies.
    """
    return isinstance(units, str) and units.strip() in _CODES


def minor_unit(code: str) -> int | None:
    """Return the ISO 4217 minor unit of a currency code, or None if it has none."""
    if code not in _MINOR_UNITS:
        raise UnitError(f"{code!r} is not an ISO 4217 currency code")
    return _MINOR_UNITS[code]


# The encoding of a currency magnitude; quantity and flow read it here.
_encoded = encoded


def _require(value: object, units: str, currency: bool) -> None:
    """Raise ContractError when a serialized magnitude does not match its units.

    ``currency`` is ``is_currency(units)``; a Flow computes it once.
    """
    if value is None:
        return
    if type(value) is str:
        if not currency:
            raise ContractError(
                f"a magnitude in {units!r} is a number, not decimal text "
                f"{value!r}; only ISO 4217 currency units take an amount",
                code=Code.CURRENCY_AMOUNT,
            )
        # Record checks run first, so the text is canonical.
        count = text_digits(value)
        if count > DIGITS:
            raise ContractError(
                f"currency amount {value} has {count} significant digits; "
                f"the limit is {DIGITS}",
                code=Code.AMOUNT_DIGITS,
            )
    elif currency:
        suggestion = _encoded(value)
        hint = f"; use {suggestion!r}" if type(suggestion) is str else ""
        raise ContractError(
            f"a magnitude in {units} is a currency amount and must be decimal "
            f"text, not {value!r}{hint}",
            code=Code.CURRENCY_AMOUNT,
        )


def round(  # noqa: A001 - the money rounding helper of ADR-023
    amount: Decimal,
    currency: str,
    *,
    places: int | None = None,
    mode: RoundingMode = RoundingMode.HALF_EVEN,
) -> Decimal:
    """Round an amount to ``places`` decimal places, by default the minor unit.

    A code with no minor unit, such as ``XAU``, needs ``places``. A negative
    ``places`` rounds to tens, hundreds and so on. ``mode`` is a ``RoundingMode``.
    """
    if type(amount) is not Decimal or not amount.is_finite():
        raise TypeError("amount must be a finite Decimal")
    if not is_currency(currency):
        raise UnitError(f"{currency!r} is not a currency; only amounts round")
    if mode not in MODES:
        raise ContractError(
            f"unknown rounding mode {mode!r}; use a RoundingMode",
            values={"mode": mode},
        )
    if places is None:
        places = minor_unit(currency.strip())
        if places is None:
            raise UnitError(f"{currency} has no minor unit; give places")
    if type(places) is not int:
        raise TypeError("places must be an int")
    exponent = Decimal(1).scaleb(-places)
    # A wide context: quantize must never round twice.
    rounded = amount.quantize(exponent, rounding=mode, context=Context(prec=1000))
    return Decimal(text(rounded))


__all__ = [
    "CONVENTION",
    "CURRENCIES",
    "DIGITS",
    "MODES",
    "RoundingMode",
    "is_currency",
    "minor_unit",
    "round",
    "to_amount",
    "to_number",
]
