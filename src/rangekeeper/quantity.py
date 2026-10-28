"""Curated unit registry: explicit compatibility without locale, exchange rates or a global registry.

The registry contains only ISO 4217 currencies; length, area and volume with SI
prefixes; time without prefixes; count, dwelling, percent and ratio; and the
aliases ``sqm``, ``sqft`` and ``pa`` (per annum). Every currency and the dwelling
count have distinct dimensions. An unknown or ambiguous string raises UnitError
with suggestions. The currency catalogue comes from pinned py-moneyed, including
historical codes. Pint is imported only when an operation needs parsing.
"""

import difflib
import math
import re
from dataclasses import dataclass, replace
from decimal import Decimal
from functools import lru_cache
from importlib.metadata import version
from typing import ClassVar

from rangekeeper.money import (
    CURRENCIES,
    ROUND_HALF_EVEN,
    _encoded,
    _require,
    is_currency,
    minor_unit,
    to_number,
)
from rangekeeper.money import round as _round
from rangekeeper.schema import records
from rangekeeper.schema.kinds import register
from rangekeeper.shared.errors import UnitError
from rangekeeper.shared.fingerprints import manifest_digest
from rangekeeper.shared.registry import Registry

_CURRENCIES = CURRENCIES

_SI_PREFIXES = (
    ("quetta", ("Q",), "1e30"),
    ("ronna", ("R",), "1e27"),
    ("yotta", ("Y",), "1e24"),
    ("zetta", ("Z",), "1e21"),
    ("exa", ("E",), "1e18"),
    ("peta", ("P",), "1e15"),
    ("tera", ("T",), "1e12"),
    ("giga", ("G",), "1e9"),
    ("mega", ("M",), "1e6"),
    ("kilo", ("k",), "1e3"),
    ("hecto", ("h",), "1e2"),
    ("deca", ("da",), "1e1"),
    ("deci", ("d",), "1e-1"),
    ("centi", ("c",), "1e-2"),
    ("milli", ("m",), "1e-3"),
    ("micro", ("µ", "μ", "u"), "1e-6"),
    ("nano", ("n",), "1e-9"),
    ("pico", ("p",), "1e-12"),
    ("femto", ("f",), "1e-15"),
    ("atto", ("a",), "1e-18"),
    ("zepto", ("z",), "1e-21"),
    ("yocto", ("y",), "1e-24"),
    ("ronto", ("r",), "1e-27"),
    ("quecto", ("q",), "1e-30"),
)

# (name, definition, symbol and aliases). The first spelling after the
# definition is the symbol. Prefixed metres and litres are added below.
_TIME = (
    ("second", "[time]", ("s", "sec")),
    ("minute", "60 * second", ("min",)),
    ("hour", "60 * minute", ("h", "hr")),
    ("day", "24 * hour", ("d",)),
    ("week", "7 * day", ("wk",)),
    ("year", "365.25 * day", ("yr",)),
    ("month", "year / 12", ()),
    ("quarter", "year / 4", ()),
)
_UNITS = (
    ("meter", "[length]", ("m", "metre")),
    ("liter", "decimeter ** 3", ("l", "L", "litre")),
    ("inch", "0.0254 * meter", ("in",)),
    ("foot", "12 * inch", ("ft",)),
    ("yard", "3 * foot", ("yd",)),
    ("mile", "1760 * yard", ("mi",)),
    ("square_meter", "meter ** 2", ("sqm", "squaremeter", "square_metre")),
    ("square_foot", "foot ** 2", ("sqft", "squarefoot")),
    ("hectare", "10000 * meter ** 2", ("ha",)),
    ("acre", "43560 * square_foot", ("ac",)),
    ("cubic_meter", "meter ** 3", ("cubic_metre",)),
    *_TIME,
    ("per_annum", "1 / year", ("pa",)),
    ("count", "[]", ()),
    ("ratio", "[]", ()),
    ("percent", "0.01", ("%",)),
    ("dwelling", "[dwelling]", ()),
)

# Spellings that a reader may expect but that the registry rejects on purpose.
_TRAPS = {
    "pct": ("%", "percent"),
    "per_cent": ("%", "percent"),
    "p.a.": ("pa",),
    "p.a": ("pa",),
    "a": ("year", "pa"),
    "annum": ("year", "pa"),
    "m2": ("sqm", "m^2"),
    "m3": ("m^3",),
    "ft2": ("sqft", "ft^2"),
    "sq": ("sqm", "sqft"),
    "bp": ("%",),
    "bps": ("%",),
}
_SCALE_WORDS = frozenset(
    {"k", "K", "m", "M", "mm", "MM", "mn", "bn", "B", "thousand", "million", "billion"}
)
_CURRENCY_SYMBOLS = {
    "US$": ("USD",),
    "A$": ("AUD",),
    "AU$": ("AUD",),
    "NZ$": ("NZD",),
    "C$": ("CAD",),
    "S$": ("SGD",),
    "HK$": ("HKD",),
    "$": ("AUD", "USD", "CAD", "NZD", "SGD", "HKD"),
    "€": ("EUR",),
    "£": ("GBP",),
    "¥": ("JPY", "CNY"),
    "₹": ("INR",),
}
_UNSIGNED = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_QUANTITY = re.compile(rf"\s*([+-]?{_UNSIGNED})\s*(.*?)\s*")
_SCALE_FACTOR = re.compile(rf"(?<![\w.^*]){_UNSIGNED}(?![\w.])")


def _prefixed(name: str, symbols: tuple[str, ...], spelling: str) -> list[tuple]:
    rows = []
    for prefix, prefix_symbols, factor in _SI_PREFIXES:
        aliases = tuple(p + s for p in prefix_symbols for s in symbols)
        aliases += (prefix + spelling,) if spelling != name else ()
        rows.append((prefix + name, f"{factor} * {name}", aliases))
    return rows


_DEFINITIONS = (
    *_UNITS,
    *_prefixed("meter", ("m",), "metre"),
    *_prefixed("liter", ("l", "L"), "litre"),
)
_CURRENCY_CODES = frozenset(_CURRENCIES)
_TIME_SPELLINGS = frozenset(
    spelling for name, _, symbols in _TIME for spelling in (name, *symbols)
)
_PREFIXED_TIME = {
    prefix + spelling: spelling
    for name, prefix_symbols, _ in _SI_PREFIXES
    for prefix in (name, *prefix_symbols)
    for spelling in _TIME_SPELLINGS
}


def _spellings(definitions: tuple[str, ...]) -> tuple[str, ...]:
    names = [
        spelling for name, _, symbols in _DEFINITIONS for spelling in (name, *symbols)
    ]
    for text in definitions:
        if text.startswith("@alias "):
            names.extend(part.strip() for part in text[7:].split("=")[1:])
        else:
            parts = [part.strip() for part in text.split("=")]
            names.extend((parts[0], *parts[2:]))
    return tuple(names)


def _format(number: float) -> str:
    return format(number, ".15g")


def _quoted(options) -> str:
    return " or ".join(repr(option) for option in options)


@lru_cache(maxsize=16)
def _registry(currencies: tuple[str, ...], definitions: tuple[str, ...] = ()):
    import pint

    registry = pint.UnitRegistry(None, autoconvert_offset_to_baseunit=False)
    for name, definition, symbols in _DEFINITIONS:
        registry.define(" = ".join((name, definition, *symbols)))
    for code in currencies:
        registry.define(f"{code} = [currency_{code}]")
    for text in definitions:
        registry.define(text)
    return registry


@register
class Quantity(records.Quantity):
    """A finite magnitude with explicit units.

    In ISO 4217 currency units the magnitude is a currency amount: a
    ``Decimal`` with at most 15 significant digits (ADR-023). Construction
    converts an ``int`` exactly, decimal text exactly and a ``float`` through
    ``money.to_amount``. In other units the magnitude is an ``int`` or a
    ``float``.
    """

    __slots__ = ()

    @classmethod
    def _coerce(cls, data: dict[str, object]) -> dict[str, object]:
        units = data.get("units")
        if not isinstance(units, str) or not is_currency(units):
            return data
        magnitude = data.get("magnitude")
        encoded = _encoded(magnitude)
        return data if encoded is magnitude else {**data, "magnitude": encoded}

    def _invariants(self) -> None:
        """Require a currency amount in currency units and a number in other units."""
        _require(self._data["magnitude"], self.units)

    @property
    def number(self) -> float:
        """Return the magnitude as a float64 for a calculation."""
        magnitude = self.magnitude
        return (
            to_number(magnitude) if isinstance(magnitude, Decimal) else float(magnitude)
        )

    def round(
        self, *, places: int | None = None, mode: str = ROUND_HALF_EVEN
    ) -> "Quantity":
        """Return the amount rounded to ``places``, by default the minor unit.

        Only currency amounts round. See ``rangekeeper.money.round``.
        """
        magnitude = self.magnitude
        if not isinstance(magnitude, Decimal):
            raise UnitError(f"{self.units!r} is not a currency; only amounts round")
        return Quantity(
            magnitude=_round(magnitude, self.units, places=places, mode=mode),
            units=self.units,
        )


@dataclass(frozen=True, slots=True)
class UnitSystem:
    """Immutable curated unit catalogue with a private lazy Pint registry.

    ``currencies`` may restrict the dependency catalogue. ``register`` and ``alias``
    return a new system with an added unit or spelling; they never change this one.
    Registry objects never escape through this interface.
    """

    currencies: tuple[str, ...] = _CURRENCIES
    definitions: tuple[str, ...] = ()
    implementation: ClassVar[str] = (
        f"rangekeeper.units/2;currencies=py-moneyed/{version('py-moneyed')}"
    )

    def __post_init__(self) -> None:
        currencies = tuple(self.currencies)
        if any(code not in _CURRENCIES for code in currencies):
            raise UnitError("unsupported currency code")
        object.__setattr__(self, "currencies", tuple(sorted(set(currencies))))
        object.__setattr__(self, "definitions", tuple(self.definitions))

    def __repr__(self) -> str:
        extra = f", definitions={len(self.definitions)}" if self.definitions else ""
        return (
            f"UnitSystem(implementation={self.implementation!r}, "
            f"currencies={len(self.currencies)}{extra})"
        )

    @property
    def fingerprint(self) -> str:
        """Return a digest of the implementation, the currencies and the definitions.

        Two systems with the same fingerprint parse and convert the same units.
        """
        manifest = {
            "implementation": self.implementation,
            "currencies": list(self.currencies),
            "definitions": list(self.definitions),
        }
        return "unit-system/v1:" + manifest_digest(manifest)

    def _spellings(self) -> tuple[str, ...]:
        return (*_spellings(self.definitions), *self.currencies)

    def _suggest(self, token: str) -> tuple[str, tuple[str, ...]]:
        """Return a reason and suggestions for one spelling the registry rejects."""
        if token in _TRAPS:
            return "is not in the curated registry", _TRAPS[token]
        if token in _PREFIXED_TIME:
            return "is a prefixed time unit; time units take no prefix", (
                _PREFIXED_TIME[token],
            )
        if token in _SCALE_WORDS:
            return "is a scale, not a unit; put the scale in the magnitude", ()
        scaled = re.fullmatch(
            r"(k|K|m|M|mm|MM|mn|bn|B)?([A-Z]{3})(k|K|m|M|mm|MM|bn)?", token
        )
        if scaled and scaled[2] in self.currencies:
            return "is a scaled currency; put the scale in the magnitude", (scaled[2],)
        if token in _CURRENCY_CODES:
            return "is a currency outside this unit system", ()
        spellings = self._spellings()
        folded = [s for s in spellings if s.casefold() == token.casefold()]
        close = difflib.get_close_matches(token, spellings, n=3, cutoff=0.6)
        return "is not in the curated registry", tuple(dict.fromkeys((*folded, *close)))

    def _parse(self, text: str):
        if not isinstance(text, str) or not text.strip():
            raise UnitError("units must be nonempty text")
        for symbol, codes in _CURRENCY_SYMBOLS.items():
            if symbol in text:
                raise UnitError(
                    f"invalid units {text!r}: {symbol!r} is an ambiguous currency "
                    f"symbol; use an ISO 4217 code such as {_quoted(codes)}",
                    suggestions=codes,
                )
        if "p.a" in text:
            raise UnitError(
                f"invalid units {text!r}: 'p.a.' is not in the curated registry; "
                "did you mean 'pa'?",
                suggestions=("pa",),
            )
        import pint

        try:
            # Pint reads "per" only between two units; a leading "per" means 1 / ...
            return _registry(self.currencies, self.definitions).parse_units(
                re.sub(r"^\s*per\s+", "1 / ", text)
            )
        except pint.errors.UndefinedUnitError as error:
            names = error.unit_names
            token = names if isinstance(names, str) else next(iter(names))
            reason, suggestions = self._suggest(token)
            hint = f"; did you mean {_quoted(suggestions)}?" if suggestions else ""
            raise UnitError(
                f"invalid units {text!r}: {token!r} {reason}{hint}",
                suggestions=suggestions,
            ) from error
        except ValueError as error:
            # Pint rejects a scale factor with a ValueError; find the number in
            # the text instead of reading Pint's message.
            if not _SCALE_FACTOR.search(text):
                raise UnitError(f"invalid units {text!r}: {error}") from error
            suggestion = self._rescaled(1, text)
            hint = f"; did you mean {suggestion!r}?" if suggestion else ""
            raise UnitError(
                f"invalid units {text!r}: units contain no numbers; "
                f"put the scale in the magnitude{hint}",
                suggestions=(suggestion,) if suggestion else (),
            ) from error
        except (
            TypeError,
            KeyError,
            ArithmeticError,
            AssertionError,
            pint.errors.PintError,
        ) as error:
            raise UnitError(f"invalid units {text!r}: {error}") from error

    def _rescaled(self, magnitude: float, text: str) -> str | None:
        """Move numbers out of unit text: ``0.5 dwelling per 100 sqm`` → ``0.005 dwelling per sqm``."""
        bare = " ".join(_SCALE_FACTOR.sub(" ", text).split())
        bare = re.sub(r"\s*/\s*", "/", bare)
        parts = re.split(r"\s+per\s+|\s*/\s*|^per\s+", text.strip(), maxsplit=1)
        grouped = f"({parts[0] or 1}) / ({parts[1]})" if len(parts) == 2 else text
        try:
            registry = _registry(self.currencies, self.definitions)
            units = registry.parse_units(re.sub(r"^per\s+", "1 / ", bare))
            value = registry.parse_expression(grouped) / registry.Quantity(1, units)
            factor = float(value.to("dimensionless").magnitude)
        except Exception:
            return None
        return f"{_format(magnitude * factor)} {bare}"

    def compatible(self, left: str, right: str) -> bool:
        """Compare dimensions; unknown/malformed units raise UnitError.

        Compatibility does not assert equal scale: metres and feet are compatible,
        but a quantity must still be explicitly converted. Currencies never convert.
        """
        return self._parse(left).dimensionality == self._parse(right).dimensionality

    def validate_units(self, text: str) -> None:
        """Require valid unit text without comparing it with a second expression."""
        self._parse(text)

    def multiply(self, left: str, right: str) -> str:
        """Return product units without removing dimensions or changing magnitudes."""
        return str(self._parse(left) * self._parse(right))

    def divide(self, numerator: str, denominator: str) -> str:
        """Return quotient units; callers remain responsible for quantity meaning."""
        return str(self._parse(numerator) / self._parse(denominator))

    def convert(self, quantity: records.Quantity, *, to: str) -> Quantity:
        """Return a new finite Quantity; leave the original units and value untouched.

        Currencies never convert; a currency amount is copied without change.
        """
        if not isinstance(quantity, records.Quantity):
            raise TypeError("quantity must be a schema Quantity")
        source, destination = self._parse(quantity.units), self._parse(to)
        if source.dimensionality != destination.dimensionality:
            raise UnitError(f"incompatible units: {quantity.units!r} and {to!r}")
        if is_currency(quantity.units) and is_currency(to):
            return Quantity(magnitude=quantity.magnitude, units=to)
        try:
            magnitude = (
                _registry(self.currencies, self.definitions)
                .Quantity(float(quantity.magnitude), source)
                .to(destination)
                .magnitude
            )
        except (ValueError, ArithmeticError) as error:
            raise UnitError(str(error)) from error
        if not math.isfinite(magnitude):
            raise UnitError("unit conversion produced a non-finite magnitude")
        return Quantity(magnitude=float(magnitude), units=to)

    def parse_quantity(self, text: str) -> Quantity:
        """Split quantity text such as ``"7 % pa"`` into a magnitude and checked units.

        The units keep their spelling. A number inside the units raises UnitError,
        and the suggestion moves the scale into the magnitude.
        """
        if not isinstance(text, str):
            raise TypeError("quantity text must be str")
        match = _QUANTITY.fullmatch(text)
        if match is None:
            raise UnitError(f"invalid quantity {text!r}: start with a number")
        magnitude, units = float(match[1]), match[2]
        if not math.isfinite(magnitude):
            raise UnitError(f"invalid quantity {text!r}: magnitude is not finite")
        if not units:
            raise UnitError(
                f"invalid quantity {text!r}: state the units, or 'dimensionless'",
                suggestions=(f"{match[1]} dimensionless",),
            )
        try:
            self._parse(units)
        except UnitError as error:
            suggestion = (
                self._rescaled(magnitude, units)
                if _SCALE_FACTOR.search(units)
                else None
            )
            if suggestion is None:
                raise
            raise UnitError(
                f"invalid quantity {text!r}: units contain no numbers; "
                f"did you mean {suggestion!r}?",
                suggestions=(suggestion,),
            ) from error
        # A currency amount is read from its text, never through float.
        return Quantity(
            magnitude=match[1] if is_currency(units) else magnitude, units=units
        )

    def minor_unit(self, code: str) -> int | None:
        """Return the ISO 4217 minor unit of a currency in this system, or None if it has none."""
        if code not in self.currencies:
            raise UnitError(f"{code!r} is not a currency in this unit system")
        return minor_unit(code)

    def register(
        self,
        name: str,
        *,
        definition: str | None = None,
        aliases: tuple[str, ...] = (),
    ) -> "UnitSystem":
        """Return a new system with one more unit; this system does not change.

        Without a definition, the unit gets its own dimension, as ``dwelling`` does.
        A definition relates it to known units, for example ``"1000 * sqm"``.
        Existing spellings cannot be redefined.
        """
        spellings = (name, *aliases)
        self._require_new(spellings)
        dimension = f"[{name}]" if definition is None else definition
        return self._extended(" = ".join((name, dimension, *aliases)), name)

    def alias(self, alias: str, unit: str) -> "UnitSystem":
        """Return a new system where ``alias`` is one more spelling of a known unit."""
        self._require_new((alias,))
        if unit not in self._spellings():
            raise UnitError(f"cannot alias unknown unit {unit!r}")
        return self._extended(f"@alias {unit} = {alias}", alias)

    def _require_new(self, spellings: tuple[str, ...]) -> None:
        known = set(self._spellings())
        for spelling in spellings:
            if not isinstance(spelling, str) or not re.fullmatch(
                r"[^\W\d]\w*", spelling
            ):
                raise UnitError(f"invalid unit name {spelling!r}")
            if spelling in known or spelling in _CURRENCY_CODES:
                raise UnitError(f"unit {spelling!r} is already defined")

    def _extended(self, definition: str, name: str) -> "UnitSystem":
        system = replace(self, definitions=(*self.definitions, definition))
        try:
            # Pint resolves definitions lazily; resolve the new unit now.
            registry = _registry(system.currencies, system.definitions)
            registry.get_dimensionality(registry.parse_units(name))
        except Exception as error:
            _registry.cache_clear()
            raise UnitError(
                f"invalid unit definition {definition!r}: {error}"
            ) from error
        return system


default_units = UnitSystem()

# Named unit systems (ADR-013, ADR-016). An installed distribution can add one in
# the entry point group ``rangekeeper.unit_systems``.
unit_systems: Registry[UnitSystem] = Registry(
    "unit_systems", UnitSystem, fingerprint=lambda system: system.fingerprint
)
unit_systems.register("default", default_units)

__all__ = ["Quantity", "UnitSystem", "default_units", "unit_systems"]
