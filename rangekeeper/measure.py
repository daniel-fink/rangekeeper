from __future__ import annotations

import pint
import moneyed


class Index:
    # registry: pint.UnitRegistry

    # def __init__(self):

    # Define Fractions:
    registry = pint.UnitRegistry(
        preprocessors=[lambda s: s.replace('%', ' percent ')]
        )
    registry.define('percent = 0.01 = %')

    # Add Additional Terms:
    registry.define('sqm = 1 * meter ** 2')
    registry.define('sqft = 1 * foot ** 2')

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


def register_currency(
        country_code: str,
        registry: pint.UnitRegistry):
    # if unit_registry is None:
    #     unit_registry = pint.UnitRegistry()

    currency = moneyed.Currency(code=country_code)

    if '[currency]' not in registry._dimensions:
        registry.define('money = [currency]')
        registry.define(
            '{0} = nan money = {0} = {1}'.format(
                currency.code,
                currency.name))
    else:
        registry.define(
            '{0} = nan money = {0} = {1}'.format(
                currency.code,
                currency.name))

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
