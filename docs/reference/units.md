# Units

A unit system parses, checks and converts unit text. `rangekeeper.quantity`
owns it. The registry is curated, as
[ADR-016](../decisions/016-safety-defaults.md) records: it contains only the units
on this page. Unknown and ambiguous text fails with suggestions.

## Contents of the registry

| Group | Units and spellings |
| --- | --- |
| Currencies | Each ISO 4217 code in the pinned py-moneyed catalogue, including historical codes, for example `AUD`, `USD` and `DEM`. Each currency has its own dimension. |
| Length | `meter` (`m`, `metre`), `inch` (`in`), `foot` (`ft`), `yard` (`yd`), `mile` (`mi`) |
| Area | `square_meter` (`sqm`, `squaremeter`), `square_foot` (`sqft`, `squarefoot`), `hectare` (`ha`), `acre` (`ac`), and any length to a power, for example `m^2` or `km ** 2` |
| Volume | `liter` (`l`, `L`, `litre`), `cubic_meter`, and any length to the power 3 |
| SI prefixes | All SI prefixes, from `quecto` (`q`) to `quetta` (`Q`), on `meter` and `liter` only: `km`, `mm`, `kL`, `GL` |
| Time | `second` (`s`, `sec`), `minute` (`min`), `hour` (`h`, `hr`), `day` (`d`), `week` (`wk`), `month`, `quarter`, `year` (`yr`). Time units take no prefix. |
| Rate | `per_annum` (`pa`) is `1 / year` |
| Counts and ratios | `count`, `ratio` and `dimensionless` (all dimensionless), `percent` (`%`) is 0.01. `dwelling` has its own dimension. |

Names accept a plural `s`, for example `meters` and `dwellings`. Symbols do not.
A year is 365.25 days, and a month is one twelfth of a year.

Unit text can use `*`, `/`, `**` or `^`, and spaces for multiplication. `per` is
division, and a leading `per` means `1 /`:

| Text | Meaning |
| --- | --- |
| `AUD pa` | AUD per year |
| `% pa` | percent per year; `7 % pa` is 0.07 per year |
| `AUD per sqm pa` | AUD per square metre per year |
| `per sqm` | `1 / sqm` |

Units contain no numbers other than exponents. Put the scale in the magnitude:
write `0.005 dwelling per sqm`, not `0.5 dwelling per 100 sqm`.

## Errors and suggestions

Each failure raises `UnitError`. Its `suggestions` attribute gives the spellings
to try instead, when the registry knows any. The message repeats them.

| Text | Result |
| --- | --- |
| `pct` | Fails; suggests `%` or `percent` |
| `$`, `A$`, `€`, `£`, `¥` | Fails: a currency symbol is ambiguous; suggests ISO 4217 codes |
| `ms`, `kyr`, `kiloyear` | Fails: time units take no prefix; suggests the bare unit |
| `kAUD`, `AUDm` | Fails: scaled currencies are not units; suggests `AUD` |
| `AUD million` | Fails: a scale is not a unit |
| `aud`, `Pa`, `SQM` | Fails; suggests the spelling with the correct case |
| `m2`, `p.a.` | Fails; suggests `sqm` or `m^2`, and `pa` |
| `dwelling per 100 sqm` | Fails; suggests `0.01 dwelling per sqm` |
| `kelvin`, `kg`, `kWh` | Fails: not in the registry |

## UnitSystem

`UnitSystem` is an immutable dataclass. `default_units` is the default instance.

| Member | Behaviour |
| --- | --- |
| `currencies` | The currency codes in the system. The default is the complete catalogue. A subset restricts the system; an unknown code raises `UnitError`. |
| `definitions` | Extra definitions added by `register` and `alias`, in order |
| `validate_units(text)` | Parses one spelling. |
| `compatible(left, right)` | Compares dimensions, not scale. Metres and feet are compatible. Different currencies are not. |
| `multiply(left, right)`, `divide(numerator, denominator)` | Return the canonical text of the product or quotient. |
| `convert(quantity, *, to)` | Returns a new finite Quantity. Incompatible units raise `UnitError`. Currencies never convert. |
| `parse_quantity(text)` | Splits quantity text, such as `"7 % pa"` or `"20e6 AUD"`, into a Quantity. The units keep their spelling. |
| `minor_unit(code)` | Returns the ISO 4217 minor unit of a currency in the system |
| `register(name, *, definition=None, aliases=())` | Returns a new system with one more unit. Without a definition, the unit has its own dimension. |
| `alias(alias, unit)` | Returns a new system with one more spelling of a known unit |

The function `rangekeeper.money.minor_unit(code)` gives the ISO 4217 minor unit
of any catalogue code: `AUD` 2, `JPY` 0, `KWD` 3, `CLF` 4. A code that ISO 4217
lists without a minor unit, such as `XAU` or `XXX`, gives `None`.
[Currency amounts](#currency-amounts) use it for rounding.

```python
from rangekeeper.quantity import default_units

storeys = default_units.register("storey").alias("level", "storey")
storeys.compatible("level", "storey")  # True
default_units.register("rood", definition="1011.7141056 * sqm")
```

`register` and `alias` do not change the original system. They refuse a spelling
that the system already has.

`UnitSystem.fingerprint` hashes the implementation, the currencies and the
definitions. Two systems with one fingerprint parse and convert the same units.

## Currency amounts

A **currency amount** is a magnitude whose units are exactly one ISO 4217 code,
for example `AUD` ([ADR-023](../decisions/023-decimal-money.md)). A Quantity uses
its own `units`; a Movement uses the `units` of its Flow. Rates such as
`AUD/m^2` and `AUD/year` are not currency amounts.

- `magnitude` is a `Decimal` for a currency amount, and an `int` or `float` for
  other units. `number` is always a float64 for calculations.
- An amount is finite and has at most 15 significant digits. Its **canonical
  text** has plain notation, no exponent, no sign for zero and no trailing
  fractional zeros: `Decimal("1.50")` is `"1.5"`.
- Construction converts an `int` and decimal text exactly, and a `float` through
  `money.to_amount`: `Quantity(magnitude=0.1 + 0.2, units="AUD")` is `0.3`.
  Decimal text in other units fails with `Code.CURRENCY_AMOUNT`; more than 15
  digits fails with `Code.AMOUNT_DIGITS`.
- `to_data()`, JSON and YAML give the canonical text as a string. The JSON reader
  is strict: a number, or text that is not canonical, fails and the error gives
  the canonical text. The YAML reader also takes a plain numeral, such as
  `1250000.50`, from its source text. A Bundle stores the text in the `string`
  field of the `Amount` option.
- Calculations use float64. `money.to_number` converts an amount for a
  calculation and `money.to_amount` converts a result back, at 15 significant
  digits, half even. Flow sums use `math.fsum`, so `Flow.total()` of three
  `0.10 AUD` movements is `0.3`. Copies (`clone`, `trim`, `clean`, same-code
  `convert`) and `negate` keep each amount exactly. Currencies never convert.
- Polars frames hold amounts as `Float64`; `io.polars.from_frame` converts them
  back with `to_amount`.

The library rounds only on request. `Quantity.round(places=None,
mode=ROUND_HALF_EVEN)`, `Flow.round(...)` and `money.round(amount, code, ...)`
round to the minor unit by default. `Flow.round` rounds each Movement, so the
total of the rounded movements can differ from the rounded total. A code without a minor unit needs `places`; a negative `places`
rounds to tens or hundreds. `mode` is one of the rounding constants of the
`decimal` module.

```python
from decimal import ROUND_HALF_UP

from rangekeeper import Quantity

price = Quantity(magnitude="0.125", units="AUD")
price.round().magnitude  # Decimal('0.12')
price.round(mode=ROUND_HALF_UP).magnitude  # Decimal('0.13')
```

## Named unit systems

`rangekeeper.quantity.unit_systems` holds unit systems by name. It follows the
[extension pattern](extensions.md). `default` is `default_units`. An installed
distribution can add a system in the entry point group `rangekeeper.unit_systems`.

```python
from rangekeeper.quantity import default_units, unit_systems

unit_systems.register("storeys", default_units.register("storey"))
unit_systems.get("storeys").validate_units("storey")
```

A Run that reaches acceptance records the unit system as an `evaluator`
implementation: `rangekeeper.unit_systems:<name>` with its fingerprint, or
`rangekeeper.quantity:UnitSystem` for an unregistered system.

## The Model's unit system

`Model(record, *, units=default_units)`, `Model.from_data` and `Model.create`
validate recorded units with the supplied system. `Model.unit_system` returns it.
A revision keeps the unit system of its predecessor.

Derived operations on a Model use `Model.unit_system` when the caller supplies no
unit system:

- `View.quantities`, `to_table` and `Reduction.execute` (and so `View.aggregate`
  and pivots);
- `Specification.lock`;
- `Composition.validate` and Specification preparation;
- `execution.rule.evaluate`;
- `Executor` and execution preparation;
- `run.validate`, which uses the unit system of the root's input Model.

Operations on records without a Model, such as `Flow.check`, `Flow.convert`,
Flow and Stream operations and `Account`, use `default_units`.

Importing domain APIs does not import Pint. The first unit operation builds the
private registry.
