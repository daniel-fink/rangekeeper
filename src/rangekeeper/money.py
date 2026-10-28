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

from moneyed import list_all_currencies

from rangekeeper.shared.amounts import (
    DIGITS,
    canonical,
    digits,
    text,
    to_amount,
    to_number,
)
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import UnitError

CURRENCIES = tuple(currency.code for currency in list_all_currencies())

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
MODES = frozenset(
    {
        ROUND_05UP,
        ROUND_CEILING,
        ROUND_DOWN,
        ROUND_FLOOR,
        ROUND_HALF_DOWN,
        ROUND_HALF_EVEN,
        ROUND_HALF_UP,
        ROUND_UP,
    }
)


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


def _broken(message: str, code: Code) -> ValueError:
    """Return the ValueError of a record rule; the record reports its code."""
    error = ValueError(message)
    error.code = code  # type: ignore[attr-defined]
    return error


def _encoded(value: object) -> object:
    """Return the canonical text of a magnitude in currency units.

    Construction converts an ``int`` exactly, a ``float`` through ``to_amount``
    and decimal text exactly. Another value is returned unchanged, and the
    record check rejects it.
    """
    if type(value) is str:
        return canonical(value) or value
    if type(value) is int:
        return text(Decimal(value))
    if type(value) is float and math.isfinite(value):
        return text(to_amount(value))
    return value


def _require(value: object, units: object) -> None:
    """Raise ValueError when a serialized magnitude does not match its units."""
    if value is None:
        return
    if type(value) is str:
        if not is_currency(units):  # type: ignore[arg-type]
            raise _broken(
                f"a magnitude in {units!r} is a number, not decimal text "
                f"{value!r}; only ISO 4217 currency units take an amount",
                Code.CURRENCY_AMOUNT,
            )
        count = digits(Decimal(value))
        if count > DIGITS:
            raise _broken(
                f"currency amount {value} has {count} significant digits; "
                f"the limit is {DIGITS}",
                Code.AMOUNT_DIGITS,
            )
    elif is_currency(units):  # type: ignore[arg-type]
        suggestion = _encoded(value)
        hint = f"; use {suggestion!r}" if type(suggestion) is str else ""
        raise _broken(
            f"a magnitude in {units} is a currency amount and must be decimal "
            f"text, not {value!r}{hint}",
            Code.CURRENCY_AMOUNT,
        )


def round(  # noqa: A001 - the money rounding helper of ADR-023
    amount: Decimal,
    currency: str,
    *,
    places: int | None = None,
    mode: str = ROUND_HALF_EVEN,
) -> Decimal:
    """Round an amount to ``places`` decimal places, by default the minor unit.

    A code with no minor unit, such as ``XAU``, needs ``places``. A negative
    ``places`` rounds to tens, hundreds and so on. ``mode`` is one of the eight
    rounding constants of the ``decimal`` module.
    """
    if type(amount) is not Decimal or not amount.is_finite():
        raise TypeError("amount must be a finite Decimal")
    if not is_currency(currency):
        raise UnitError(f"{currency!r} is not a currency; only amounts round")
    if mode not in MODES:
        raise ValueError(f"unknown rounding mode {mode!r}")
    if places is None:
        places = minor_unit(currency.strip())
        if places is None:
            raise ValueError(f"{currency} has no minor unit; give places")
    if type(places) is not int:
        raise TypeError("places must be an int")
    exponent = Decimal(1).scaleb(-places)
    # A wide context: quantize must never round twice.
    rounded = amount.quantize(exponent, rounding=mode, context=Context(prec=1000))
    return Decimal(text(rounded))


__all__ = [
    "CURRENCIES",
    "DIGITS",
    "MODES",
    "is_currency",
    "minor_unit",
    "round",
    "to_amount",
    "to_number",
]
