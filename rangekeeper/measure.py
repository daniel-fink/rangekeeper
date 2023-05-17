from __future__ import annotations

import locale

import pint
#from pint.definitions import UnitDefinition
#from pint.converters import ScaleConverter
import moneyed


class Index:
    # Define Fractions:
    registry = pint.UnitRegistry()
    #     preprocessors=[lambda s: s.replace('%', ' percent ')]
    #     )
    # # registry.define('percent = 0.01 * dimensionless = %')
    # registry.define(UnitDefinition('percent', '%', (), ScaleConverter(1 / 100.0)))

    # Add Additional Terms:
    registry.define('squaremeter = 1 m**2 = m2 = sqm')
    registry.define('squarefoot = 1 foot**2 = ft2 = sqft')

    # Define Domain Units:
    registry.define('zone = [space]')
    registry.define('parking_stall = 1 * zone')

    # self.registry = registry

    # # Define Scalar:
    # scalar = Measure(
    #     name='Scalar Quantity',
    #     definition='Dimensionless or Unitless Quantity',
    #     units=pint.UnitRegistry().dimensionless)

    # @staticmethod


def remove_dimension(
        quantity: pint.Quantity,
        dimension: str,
        registry: pint.UnitRegistry = None) -> pint.Quantity:
    """
    Remove a dimension from the units of a quantity. Specify the dimension as a string wrapped in square brackets (['']).
    """
    if dimension in quantity.dimensionality:
        for unit_str in quantity.units._units:
            units = registry.Unit(unit_str) if registry is not None else pint.Unit(unit_str)
            if units.dimensionality == dimension:
                if quantity.dimensionality[dimension] == -1:
                    return quantity * units
                elif quantity.dimensionality[dimension] == 1:
                    return quantity / units
                else:
                    raise NotImplementedError(
                        'Error: Dimension reduction currently only works for single-order (^1 or ^-1) dimensions.')
    else:
        return quantity


def multiply_units(
        units: [pint.Unit],
        registry: pint.UnitRegistry = None) -> pint.Unit:
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
        registry: pint.UnitRegistry):
    # if unit_registry is None:
    #     unit_registry = pint.UnitRegistry()

    currency = moneyed.Currency(code=locale.localeconv()['int_curr_symbol'].strip())

    if '[currency]' not in registry._dimensions:
        registry.define('money = [currency]')
        registry.define(
            '{0} = nan money = {0} = {1}'.format(
                ''.join(currency.code.split()),
                ''.join(currency.name.split())))
    else:
        registry.define(
            '{0} = nan money = {0} = {1}'.format(
                ''.join(currency.code.split()),
                ''.join(currency.name.split())))

    return Measure(
        name=currency.name,
        definition='Currency of {0}'.format(currency.countries),
        units=registry[currency.code].units)


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

    def __init__(
            self,
            name: str,
            units: pint.Unit,
            definition: str = None):
        self.name = name
        self.units = units
        self.definition = definition

    def __str__(self):
        return 'Rangekeeper Measure: "{0}". {1}. Units: {2}'.format(
            self.name,
            self.definition,
            self.units)

    def __hash__(self):
        return hash((self.name, self.units.__hash__()))

    def __eq__(self, other):
        return (self.name == other.name and
                self.units == other.units)