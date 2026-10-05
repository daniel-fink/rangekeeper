"""Explicit unit compatibility without locale, exchange rates, or a global registry.

The currency catalogue is a pinned py-moneyed 3.0 snapshot (including historical
codes). Every currency and dwelling count have distinct dimensions. Pint is imported
only when an operation needs parsing; importing the new domain API stays lightweight.
"""

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import json
import math
from typing import ClassVar

from ._schema.records import Quantity
from .errors import UnitError

_CURRENCIES = tuple(
    json.loads(files("rangekeeper").joinpath("_currencies.json").read_text())["codes"]
)


@lru_cache(maxsize=16)
def _registry(currencies: tuple[str, ...]):
    import pint

    registry = pint.UnitRegistry()
    registry.define("squaremeter = meter ** 2 = sqm = m2")
    registry.define("squarefoot = foot ** 2 = sqft = ft2")
    registry.define("dwelling = [dwelling]")
    for code in currencies:
        registry.define(f"{code} = [currency_{code}]")
    return registry


@dataclass(frozen=True, slots=True)
class UnitSystem:
    """Immutable supported-currency selection with a private lazy Pint registry.

    ``currencies`` may restrict the bundled catalogue; it cannot introduce arbitrary
    aliases or exchange rules. Registry objects never escape through this interface.
    """

    currencies: tuple[str, ...] = _CURRENCIES
    implementation: ClassVar[str] = "rangekeeper.units/1;currencies=py-moneyed/3.0"

    def __post_init__(self) -> None:
        currencies = tuple(self.currencies)
        if any(code not in _CURRENCIES for code in currencies):
            raise UnitError("unsupported currency code")
        object.__setattr__(self, "currencies", tuple(sorted(set(currencies))))

    def __repr__(self) -> str:
        return f"UnitSystem(implementation={self.implementation!r}, currencies={len(self.currencies)})"

    def _parse(self, text: str):
        if not isinstance(text, str) or not text.strip():
            raise UnitError("units must be nonempty text")
        try:
            return _registry(self.currencies).parse_units(text)
        except (ValueError, TypeError, KeyError, ArithmeticError) as error:
            raise UnitError(f"invalid units {text!r}: {error}") from error
        except Exception as error:
            # Pint's exception hierarchy is imported lazily with the registry.
            import pint

            if isinstance(error, pint.errors.PintError):
                raise UnitError(f"invalid units {text!r}: {error}") from error
            raise

    def compatible(self, left: str, right: str) -> bool:
        """Compare dimensions; unknown/malformed units raise UnitError.

        Compatibility does not assert equal scale: metres and feet are compatible,
        but a quantity must still be explicitly converted. Currencies never convert.
        """
        return self._parse(left).dimensionality == self._parse(right).dimensionality

    def multiply(self, left: str, right: str) -> str:
        """Return product units without removing dimensions or changing magnitudes."""
        return str(self._parse(left) * self._parse(right))

    def divide(self, numerator: str, denominator: str) -> str:
        """Return quotient units; callers remain responsible for quantity meaning."""
        return str(self._parse(numerator) / self._parse(denominator))

    def convert(self, quantity: Quantity, *, to: str) -> Quantity:
        """Return a new finite Quantity; leave the original units and value untouched."""
        if not isinstance(quantity, Quantity):
            raise TypeError("quantity must be a schema Quantity")
        source, destination = self._parse(quantity.units), self._parse(to)
        if source.dimensionality != destination.dimensionality:
            raise UnitError(f"incompatible units: {quantity.units!r} and {to!r}")
        try:
            magnitude = (
                _registry(self.currencies)
                .Quantity(quantity.magnitude, source)
                .to(destination)
                .magnitude
            )
        except (ValueError, ArithmeticError) as error:
            raise UnitError(str(error)) from error
        if not math.isfinite(magnitude):
            raise UnitError("unit conversion produced a non-finite magnitude")
        return Quantity(magnitude=float(magnitude), units=to)


default_units = UnitSystem()
