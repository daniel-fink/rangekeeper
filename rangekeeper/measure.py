from __future__ import annotations

import pint
import moneyed


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


scalar = Measure(
    name='Scalar Quantity',
    definition='Dimensionless or Unitless Quantity',
    units=pint.UnitRegistry().dimensionless)


def add_currency(
        country_code: str,
        unit_registry: pint.UnitRegistry = None) -> Measure:
    if unit_registry is None:
        unit_registry = pint.UnitRegistry()

    currency = moneyed.Currency(code=country_code)

    if '[currency]' not in unit_registry._dimensions:
        unit_registry.define('money = [currency]')
        unit_registry.define(
            '{0} = nan money = {0} = {1}'.format(
                currency.code,
                currency.name))
    else:
        unit_registry.define(
            '{0} = nan money = {0} = {1}'.format(
                currency.code,
                currency.name))

    return Measure(
        name=currency.name,
        definition='Currency of {0}'.format(currency.countries),
        units=unit_registry[currency.code].units)

