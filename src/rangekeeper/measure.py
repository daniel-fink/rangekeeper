from __future__ import annotations
import locale

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


class Measure:
    name: str
    definition: str
    units: pint.Unit

    def __init__(self, name: str, units: pint.Unit, definition: str = None):
        self.name = name
        self.units = units
        self.definition = definition

    def __str__(self):
        return 'Rangekeeper Measure: "{0}". {1}. Units: {2}'.format(
            self.name, self.definition, self.units
        )

    def __hash__(self):
        return hash((self.name, self.units.__hash__()))

    def __eq__(self, other):
        return self.name == other.name and self.units == other.units
