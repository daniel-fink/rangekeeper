from __future__ import annotations

from typing import Union
import pint
import moneyed
import aenum


class Measurement:
    name: str
    definition: str
    units: Union[pint.Unit, moneyed.Currency]

    def __init__(
            self,
            name: str,
            units: Union[pint.Unit, moneyed.Currency],
            definition: str = None):
        self.name = name
        self.units = units
        self.definition = definition

    @classmethod
    def currency_from_country_code(cls, code: str) -> Measurement:
        currency = moneyed.Currency(code=code)
        return cls(
            name=currency.name,
            units=currency,
            definition='Monetary Currency')

    @staticmethod
    def Scalar() -> Measurement:
        return Measurement(
            name='Scalar Quantity',
            definition='Dimensionless or Unitless Quantity',
            units=pint.UnitRegistry().dimensionless)

