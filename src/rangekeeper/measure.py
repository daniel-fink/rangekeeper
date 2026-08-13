from __future__ import annotations
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import locale
from typing import Any

import pint
import moneyed


class Index:
    # Define Fractions:
    registry = pint.UnitRegistry()

    # Add Additional Terms:
    # registry.define("percent = 0.01 * dimensionless = % = pct") # Remove this because it causes issues?
    registry.define("squaremeter = 1 m**2 = m2 = sqm")
    registry.define("squarefoot = 1 foot**2 = ft2 = sqft")

    # Define Domain Units:
    # registry.define("zone = [space]")
    # registry.define("parking_stall = 1 * zone")


def to_filtered(
    quantity: pint.Quantity,
    exclude=("percent",),
) -> pint.Quantity:
    units = quantity._units
    excluded = [name for name in units if name in set(exclude)]
    new_units = units.remove(excluded) if excluded else units
    return quantity.to(new_units)


def remove_dimension(
    quantity: pint.Quantity,
    dimension: str,
    registry: pint.UnitRegistry = None,
) -> pint.Quantity:
    """
    Remove a dimension from the units of a quantity. Specify the dimension as a string wrapped in square brackets (['']).
    """
    if dimension in quantity.dimensionality:
        for unit_str in quantity.units._units:
            units = (
                registry.Unit(unit_str) if registry is not None else pint.Unit(unit_str)
            )
            if units.dimensionality == dimension:
                if quantity.dimensionality[dimension] == -1:
                    return quantity * units
                elif quantity.dimensionality[dimension] == 1:
                    return quantity / units
                else:
                    raise NotImplementedError(
                        "Error: Dimension reduction currently only works for single-order (^1 or ^-1) dimensions."
                    )
    else:
        return quantity


def multiply_units(
    units: [pint.Unit],
    registry: pint.UnitRegistry = None,
) -> pint.Unit:
    """
    Multiply units together.
    """
    registry = registry if registry is not None else pint.UnitRegistry()
    quantities = [registry.Quantity(1, unit) for unit in units]
    result = 1 * registry.dimensionless
    for quantity in quantities:
        result *= quantity
    return result.units


def register_currency(
    registry: pint.UnitRegistry,
    code: str = None,
) -> Measure:
    """
    Register a currency in the pint UnitRegistry.
    If no code is provided, it will use the current locale's currency.
    """

    if code is None:
        # Use the locale's currency code
        code = locale.localeconv()["int_curr_symbol"].strip()

    currency = moneyed.Currency(code=code)

    if "[currency]" not in registry._dimensions:
        registry.define("money = [currency]")
        registry.define(
            "{0} = nan money = {0} = {1}".format(
                "".join(currency.code.split()), "".join(currency.name.split())
            )
        )
    else:
        registry.define(
            "{0} = nan money = {0} = {1}".format(
                "".join(currency.code.split()), "".join(currency.name.split())
            )
        )

    return Measure(
        code=f"currency.{currency.code.lower()}",
        name=currency.name,
        definition="Currency of {0}".format(currency.countries),
        units=registry.parse_units(currency.code),
    )


#
# class Quantity(pint.Quantity):
#     def __init__(
#             self,
#             value,
#             units: pint.Unit
#             ):
#         """
#         value : str, pint.Quantity or any numeric type. Value of the physical quantity to be created.
#         units :
#         """
#         super.__init__()


@dataclass(frozen=True, eq=False)
class Measure:
    """A coded measurement definition with stable identity."""

    code: str
    name: str
    units: pint.Unit
    definition: str | None = None
    tags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        self._validate_required_text(self.code, "code")
        self._validate_required_text(self.name, "name")
        if not isinstance(self.units, pint.Unit):
            raise TypeError("units must be a Pint Unit")
        if self.definition is not None and not isinstance(self.definition, str):
            raise TypeError("definition must be a string or None")

        tags = frozenset(self.tags)
        if any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            raise ValueError("tags must contain only non-empty strings")
        object.__setattr__(self, "tags", tags)

    @staticmethod
    def _validate_required_text(value: str, field: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string")
        if not value.strip():
            raise ValueError(f"{field} must not be empty")

    def __str__(self) -> str:
        return (
            f'Rangekeeper Measure: "{self.name}" [{self.code}]. '
            f"{self.definition}. Units: {self.units}"
        )

    def __hash__(self) -> int:
        return hash(self.code)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Measure):
            return NotImplemented
        return self.code == other.code

    def assert_consistent_with(self, other: Measure) -> None:
        """Reject conflicting definitions that reuse this measure's code."""
        if not isinstance(other, Measure):
            raise TypeError("other must be a Measure")
        if self.code != other.code:
            raise ValueError("measures with different codes cannot be compared")

        conflicts = []
        if self.units.dimensionality != other.units.dimensionality:
            conflicts.append("units")
        if self.definition != other.definition:
            conflicts.append("definition")
        if conflicts:
            fields = ", ".join(conflicts)
            raise ValueError(
                f"conflicting definitions for measure code {self.code!r}: {fields}"
            )

    def validate_quantity(self, quantity: pint.Quantity) -> None:
        if not isinstance(quantity, pint.Quantity):
            raise TypeError("quantity must be a Pint Quantity")
        if quantity.dimensionality != self.units.dimensionality:
            raise pint.DimensionalityError(quantity.units, self.units)

    def to_record(self) -> dict[str, object]:
        return {
            "code": self.code,
            "name": self.name,
            "units": str(self.units),
            "definition": self.definition,
            "tags": sorted(self.tags),
        }

    @classmethod
    def from_record(
        cls,
        record: Mapping[str, Any],
        *,
        registry: pint.UnitRegistry = Index.registry,
    ) -> Measure:
        if not isinstance(record, Mapping):
            raise TypeError("measure record must be a mapping")
        try:
            code = record["code"]
            name = record["name"]
            units = record["units"]
        except KeyError as error:
            raise ValueError(f"measure record is missing {error.args[0]!r}") from error
        if not isinstance(units, str):
            raise TypeError("serialized measure units must be a string")

        tags: Iterable[str] = record.get("tags", ())
        return cls(
            code=code,
            name=name,
            units=registry.parse_units(units),
            definition=record.get("definition"),
            tags=frozenset(tags),
        )
