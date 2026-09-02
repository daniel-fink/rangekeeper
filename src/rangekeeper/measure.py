from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
import locale
from uuid import UUID, uuid4

import moneyed
import pint

from . import validate


class Index:
    registry = pint.UnitRegistry()
    registry.define("squaremeter = 1 m**2 = m2 = sqm")
    registry.define("squarefoot = 1 foot**2 = ft2 = sqft")


class QuantityKind(Enum):
    AREA = "area"
    LENGTH = "length"
    CURRENCY = "currency"
    COUNT = "count"
    RATIO = "ratio"
    OTHER = "other"


class AggregationRule(Enum):
    SUM = "sum"
    MEAN = "mean"
    MEDIAN = "median"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    NONE = "none"


@dataclass(frozen=True, slots=True, kw_only=True)
class Measure:
    """A normalized measurement definition with UUID identity."""

    id: UUID = field(default_factory=uuid4)
    code: str
    name: str
    units: pint.Unit
    quantity_kind: QuantityKind = QuantityKind.OTHER
    aggregation: AggregationRule = AggregationRule.NONE
    definition: str | None = None
    tags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        validate.require_uuid(self.id, "id")
        validate.require_text(self.code, "Measure.code")
        validate.require_text(self.name, "Measure.name")
        if not isinstance(self.units, pint.Unit):
            raise TypeError("units must be a Pint Unit")
        if not isinstance(self.quantity_kind, QuantityKind):
            raise TypeError("quantity_kind must be a QuantityKind")
        if not isinstance(self.aggregation, AggregationRule):
            raise TypeError("aggregation must be an AggregationRule")
        validate.optional_text(self.definition, "definition")
        tags = frozenset(self.tags)
        if any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            raise ValueError("tags must contain only non-empty strings")
        object.__setattr__(self, "tags", tags)
        self._validate_quantity_kind()

    def _validate_quantity_kind(self) -> None:
        dimensionality = self.units.dimensionality
        expected = {
            QuantityKind.AREA: Index.registry.meter**2,
            QuantityKind.LENGTH: Index.registry.meter,
            QuantityKind.COUNT: Index.registry.dimensionless,
            QuantityKind.RATIO: Index.registry.dimensionless,
        }.get(self.quantity_kind)
        if expected is not None and dimensionality != expected.dimensionality:
            raise ValueError(
                f"units {self.units!s} are incompatible with "
                f"quantity kind {self.quantity_kind.value!r}"
            )
        if (
            self.quantity_kind is QuantityKind.CURRENCY
            and "[currency]" not in dimensionality
        ):
            raise ValueError(
                "currency measures require units with [currency] dimensionality"
            )

    def validate_quantity(self, quantity: pint.Quantity) -> None:
        if not isinstance(quantity, pint.Quantity):
            raise TypeError("quantity must be a Pint Quantity")
        if quantity.dimensionality != self.units.dimensionality:
            raise pint.DimensionalityError(quantity.units, self.units)


def to_filtered(quantity: pint.Quantity, exclude=("percent",)) -> pint.Quantity:
    units = quantity._units
    excluded = [name for name in units if name in set(exclude)]
    new_units = units.remove(excluded) if excluded else units
    return quantity.to(new_units)


def remove_dimension(
    quantity: pint.Quantity,
    dimension: str,
    registry: pint.UnitRegistry | None = None,
) -> pint.Quantity:
    if dimension not in quantity.dimensionality:
        return quantity
    for unit_str in quantity.units._units:
        units = registry.Unit(unit_str) if registry is not None else pint.Unit(unit_str)
        if units.dimensionality == dimension:
            order = quantity.dimensionality[dimension]
            if order == -1:
                return quantity * units
            if order == 1:
                return quantity / units
            raise NotImplementedError(
                "dimension reduction currently supports only order 1 or -1"
            )
    return quantity


def multiply_units(
    units: Iterable[pint.Unit],
    registry: pint.UnitRegistry | None = None,
) -> pint.Unit:
    registry = registry if registry is not None else pint.UnitRegistry()
    result = 1 * registry.dimensionless
    for unit in units:
        result *= registry.Quantity(1, unit)
    return result.units


def register_currency(
    registry: pint.UnitRegistry,
    code: str | None = None,
) -> Measure:
    code = locale.localeconv()["int_curr_symbol"].strip() if code is None else code
    currency = moneyed.Currency(code=code)
    if "[currency]" not in registry._dimensions:
        registry.define("money = [currency]")
    registry.define(
        "{0} = nan money = {0} = {1}".format(
            "".join(currency.code.split()), "".join(currency.name.split())
        )
    )
    return Measure(
        code=f"currency.{currency.code.lower()}",
        name=currency.name,
        definition=f"Currency of {currency.countries}",
        units=registry.parse_units(currency.code),
        quantity_kind=QuantityKind.CURRENCY,
        aggregation=AggregationRule.SUM,
    )
