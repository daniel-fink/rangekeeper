# ADR-023: Store currency amounts as Decimal and calculate in float64

Status: proposed. Recorded: 2026-10-27.

## Problem

[ADR-017](017-api-and-formats.md#money) decides the money rules. Currency
amounts are Decimal in records and in their serialised forms. Calculations use
float64 inside, with compensated summation. Conversion happens only at explicit
calculation boundaries. Rounding follows explicit rules, with currency minor
units. JSON and Parquet must round-trip exactly. ADR-017 does not give the
design. Issue [#117](https://github.com/daniel-fink/rangekeeper/issues/117)
asks for it.

These facts from `develop` at `1e32b8d` constrain the design:

- **Schema and generators disagree.** `Quantity.magnitude` and
  `Movement.magnitude` have the LinkML range `decimal`. The Python generator
  maps `decimal` to `int | float`. The C# generator maps it to `decimal`.
- **`decimal` is not only money.** `Settings.relative_tolerance` and
  `Settings.time_limit` also use `decimal`.
- **Units are separate from the magnitude.** A Quantity has its own `units`. A
  Movement takes its units from its Flow.
- **Currencies do not convert.** `UnitSystem` gives each ISO 4217 code its own
  dimension, so AUD and USD are incompatible.
- **Comparison is type-sensitive.** `exact_equal` treats `0` and `0.0` as
  different, and `0.0` and `-0.0` as different.
- **The Bundle has a precedent.** Parquet stores integer magnitudes as text to
  keep arbitrary precision.
- **float64 shows binary noise.** The sum of three 0.10 AUD movements is
  `0.30000000000000004`. A JavaScript reader parses JSON numbers as doubles and
  loses digits after about 15 significant digits.
- **The example Model has no money.** `examples/data/mixed_use_property/model.json`
  has 144 Quantities, all in m, m² or m³, and no Flows.

## Choice

### Currency amounts

1. A **currency amount** is a magnitude whose units are exactly one ISO 4217
   code in the unit system, for example `AUD`. A Quantity uses its own `units`.
   A Movement uses the `units` of its Flow.
2. Currency amounts are Decimal. All other magnitudes stay float64, with
   `int | float` in Python. This includes rates such as `AUD/m^2` and
   `AUD/year`, ratios, percentages, geometry and time.
3. The curated unit registry ([#149](https://github.com/daniel-fink/rangekeeper/issues/149))
   defines no scaled currency units, such as `kAUD` or `AUD million`. An
   attempt to use one fails, and the suggestion gives the plain code.
4. A code with no ISO 4217 minor unit, such as `XAU` or `XXX`, is still a
   currency amount. It has no default rounding.
5. `Settings.relative_tolerance` and `Settings.time_limit` change from `decimal`
   to `double`. Distribution parameters stay `double`.

### Value rules

1. A currency amount is finite. It has at most **15 significant digits**, with
   any number of decimal places. Trailing zeros are not significant:
   `1481480.40` has 8 significant digits and `1E+22` has 1.
2. Fifteen digits is the float64 decimal precision (`DBL_DIG`). So every valid
   amount converts to float64 and back without change. Cents stay exact up to
   10¹³ units.
3. Each amount has one **canonical text**: plain notation, no exponent, no
   sign for zero or positive values, no leading zeros and no trailing
   fractional zeros. The pattern is
   `^(0|-?(0\.[0-9]*[1-9]|[1-9][0-9]*(\.[0-9]*[1-9])?))$`.
4. Two amounts are equal when their Decimal values are equal. `1.50` and `1.5`
   are the same record value. Because `to_data()` gives canonical text,
   `exact_equal` compares amounts with no change.

| Input | Canonical text | Valid |
| --- | --- | --- |
| `Decimal("1.50")` | `"1.5"` | Yes |
| `Decimal("-0.00")` | `"0"` | Yes |
| `Decimal("1E+3")` | `"1000"` | Yes |
| `Decimal("0.0000001")` | `"0.0000001"` | Yes |
| `Decimal("1234567890.123456")` | — | No: 16 significant digits |
| `Decimal("NaN")` | — | No: not finite |

### Python type and API

1. Use `decimal.Decimal` inside the existing `Quantity` and `Movement` records.
   Do not add a separate money type.
2. `magnitude` returns the exact record value: `Decimal` for a currency amount,
   `int | float` for other magnitudes. Its annotation is
   `Decimal | int | float`.
3. `number` returns a float64 for calculations. `Movement.number` exists today;
   `Quantity.number` is new.
4. Construction accepts these inputs:

   | Input | Currency units | Other units |
   | --- | --- | --- |
   | `Decimal` | Exact. More than 15 significant digits fails. | Fails |
   | `int` | Exact `Decimal` | Kept as `int` |
   | `str` | Parsed exactly as a decimal numeral | Fails |
   | `float` | Boundary conversion (below) | Kept as `float` |
   | `bool`, NaN, infinity | Fails | Fails |

5. A record has no arithmetic operators ([ADR-011](011-records-and-validation.md)).
   Python raises `TypeError` for `Decimal` with `float`. Library code never
   mixes the two. It converts at a named boundary.
6. A public money module gives the boundary and rounding helpers. The ADR-010
   move map chooses its import path; the working name is `rangekeeper.money`:
   - `is_currency(units) -> bool`;
   - `minor_unit(code) -> int | None`;
   - `to_number(amount) -> float` and `to_amount(number) -> Decimal`;
   - `round(...)`, also available as `Quantity.round` and `Flow.round`.

#### Flow and Stream operations

| Operation | Inside | Result for a currency Flow |
| --- | --- | --- |
| `clone`, `trim`, `trim_empty`, `clean`, `extent` | No arithmetic | Magnitudes copied unchanged |
| `negate` | Sign change | Exact |
| `convert` to the same code | No arithmetic | Unchanged. Currencies never convert. |
| `total`, `scale`, `difference`, `collapse` | float64 with `math.fsum` | Each result through `to_amount` |
| `from_events`, `from_periods` | Construction | Inputs as in the construction table |
| `io.polars.to_frame`, Stream frames, Flux | `Float64` columns | Not records |
| `io.polars.from_frame` with currency units | None | Each value through `to_amount` |
| `display` and tables | None | Text at the minor unit. The record does not change. |

Flow and Stream use the same float64 path, so their results agree.

### Encodings

| Form | Currency amount | Other magnitude |
| --- | --- | --- |
| Python `to_data()` | `str`, canonical text | `int` or `float`, as today |
| JSON | String, canonical text: `"magnitude": "1250000.5"` | Number, as today |
| YAML writer | Quoted string, canonical text | Number |
| YAML reader | Quoted string or plain numeral, from its exact source text | Number |
| Parquet, Bundle format 1 | `string` field with canonical text | Existing `integer` and `number` fields |
| Fingerprint `encode` | `["decimal", canonical text]` | `["int", …]` or `["float", …]` |
| C# example | `System.Decimal` | `double` |

1. **JSON is strict.** The reader rejects a number for a currency amount, a
   string for another magnitude, and text that is not canonical. The error
   gives the canonical text.
2. **YAML is for authoring.** The reader takes a numeral from its source text,
   never through float. It accepts text that is not canonical, such as
   `1250000.00`, and stores the canonical form.
3. **Parquet** adds a `decimal: string` field to the physical union of the
   magnitude slots. The slot tag selects it for currency amounts. For analysis,
   a reader casts the text to `DECIMAL(38, s)` or `DOUBLE`.
4. **LinkML.** `common.yaml` adds a type for currency amount text:

   ```yaml
   types:
     Amount:
       typeof: string
       base: Decimal
       uri: xsd:decimal
       pattern: ^(0|-?(0\.[0-9]*[1-9]|[1-9][0-9]*(\.[0-9]*[1-9])?))$
       description: Canonical decimal text of a currency amount.
   ```

   The magnitude slots become `any_of: [{range: Amount}, {range: double}]`. The
   schema no longer uses the `decimal` range.
5. **JSON Schema.** A magnitude is a number or a string with the `Amount`
   pattern. JSON Schema cannot use the unit registry. So record validation
   ([ADR-011](011-records-and-validation.md)) checks the pairing with the
   units, with the code `currency_amount`. It checks the digit limit with the
   code `amount_digits`.
6. **C# example.** Every valid amount below 7.9 × 10²⁸, with at most 28 decimal
   places, fits `System.Decimal`. The example rejects other amounts with an
   error. It is an unsupported example ([ADR-010](010-layers-and-packages.md)).
7. **Round trip.** `loads(dumps(x))` and a Bundle write and read give records
   that satisfy `exact_equal` with the original.

### Boundaries

| Boundary | Rule | Used by |
| --- | --- | --- |
| Amount to float (`to_number`) | `float(Decimal)`, correctly rounded | `number`, Polars frames, Flux, solver compiler (`Affine` and `Compiled`), acceptance |
| Float to amount (`to_amount`) | Round to 15 significant digits, half even, then canonical text. A value that is not finite raises `NumericalError`. | Flow results, `from_frame`, reducers, solver publication, Diagnostic `residual` and `tolerance`, construction from `float` |
| Exact copy | No conversion | IO, assignments, `trim`, `clean`, `clone`, same-code `convert` |

1. `to_amount(to_number(a)) == a` for every valid amount `a`.
2. `to_number(to_amount(x))` differs from `x` by at most 5 × 10⁻¹⁵ · |x|.
   This is the 15-digit conversion, not rounding to minor units.
3. The solver backend works in float64. Publication writes each currency
   unknown through `to_amount`. It copies each assigned amount from its
   Specification without conversion.

#### Evidence

1. The format reset adds the value `convention` to `ImplementationKind`. It
   means a numerical convention that affects results.
2. Each Run with a Runtime records
   `Implementation(kind=convention, name="rangekeeper.money", version="1")`.
3. Version 1 means: float64 inside; `math.fsum` for sums; `to_number` correctly
   rounded; `to_amount` at 15 significant digits, half even. A change to one of
   these rules needs a new version.
4. A Run does not record a conversion for each value.

#### Tolerances for solved money

1. Acceptance keeps `Tolerances(absolute=1e-8, relative=1e-9)`. It compares in
   float64 on `to_number` values, in the units of the left side.
2. The `to_amount` error is at most 5 × 10⁻¹⁵ relative. This is far below the
   relative tolerance, so the conversion cannot change an acceptance result.
3. Acceptance compares assignments exactly, as Decimal values.
4. Acceptance never rounds to minor units. A later feature that rounds Run
   outputs must check the outputs before it rounds them.
5. Contract fixtures (`tests/contracts`) compare records with `exact_equal`.
   They compare calculated values in float64, with a stated tolerance.

### Rounding

1. The curated unit registry (#149) gives each code its ISO 4217 minor unit:
   `AUD` 2, `JPY` 0, `KWD` 3, `CLF` 4. `MGA` and `MRU` use 2, as ISO 4217
   lists them. `XAU` and `XXX` have none.
2. `Quantity.round(*, places=None, mode=ROUND_HALF_EVEN)` and `Flow.round(...)`
   return new records. They accept currency amounts only.
3. `places` defaults to the minor unit. A code with no minor unit needs
   `places`. A negative `places` value rounds to tens, hundreds and so on.
4. `mode` accepts the eight rounding constants of the `decimal` module. The
   default is `ROUND_HALF_EVEN`.
5. The library never rounds inside a calculation, during IO or when it creates
   a record. It rounds only on request. Display formats text at the minor unit
   and does not change the record.
6. `Flow.round` rounds each Movement. The total of the rounded movements can
   differ from the rounded total. A rounding that keeps the total is not part
   of this design.

## Worked examples

1. **Sum.** A Flow in `AUD` has three movements of `0.10`. `Flow.total()` adds
   `0.1` three times with `fsum` and gets `0.30000000000000004`. `to_amount`
   gives `"0.3"`.
2. **Growth.** `1000 AUD × 1.03¹²` in float64 is `1425.7608868461793`.
   `to_amount` gives `"1425.76088684618"`. `round()` gives `"1425.76"`.
3. **Split.** `100 AUD` scaled by `1/3` gives `"33.3333333333333"` for each of
   three movements. `Flow.round()` gives three movements of `"33.33"`. Their
   total is `"99.99"`, and the rounded total of the original is `"100"`.
4. **Rate.** A Quantity of `450.5 AUD/m^2` is a float. Multiplied by
   `1200 m^2`, the result has units `AUD`, so it becomes the amount `"540600"`.
5. **Rounding modes.** For `0.125 AUD`, `ROUND_HALF_EVEN` gives `0.12`;
   `ROUND_HALF_UP` (away from zero, as in Excel `ROUND`) gives `0.13`. For
   `1234.5 JPY` the default gives `1234`. For `1.2345 KWD` it gives `1.234`.
6. **Encodings of one Movement in an `AUD` Flow:**

   ```json
   {"id": "…", "date": "2027-01-01", "magnitude": "1250000.5"}
   ```

   ```yaml
   - id: …
     date: 2027-01-01
     magnitude: "1250000.5"   # the reader also accepts 1250000.50
   ```

   In Parquet, the magnitude union has the tag for `Amount` and the field
   `decimal = "1250000.5"`.
7. **Solver evidence.** An equality constraint in `AUD` leaves the float
   residual `3.2e-11`. The Diagnostic records `residual` as `"0.000000000032"`
   and `tolerance` through `to_amount`. Both have units `AUD`.

## Performance

[Measured](../research/decimal-money-2026-10-27/README.md) on 2026-10-27 with
Python 3.14.2, Polars 1.44.2 and PyArrow 23.0.1:

| Operation | Today (float64) | Decimal cost |
| --- | --- | --- |
| `Flow.from_events`, 120 movements, with `check` | 6.9 ms | Parse 13 µs; `to_number` 12 µs; `to_amount` 48 µs |
| `io.polars.to_frame`, 120 movements | 0.91 ms | Cast from Decimal to `Float64`: 1 µs |
| JSON text of 120 magnitudes | 72 µs for the Flow | 14 µs to write; 19 µs to read |
| Example Model: JSON read and write | 79 ms and 82 ms | No currency amounts; 85 µs if all 144 magnitudes converted |
| Example Model: Bundle write and read | 395 ms and 216 ms | No currency amounts |
| Parquet, 10⁶ values: size, write, read | 7.0 MB, 27 ms, 11 ms (`float64`) | 5.3 MB, 56 ms, 22 ms (`string`) |

At record sizes, Decimal adds less than 1 % to construction and IO. The
calculations do not change, because they stay in float64.

## Acceptance tests for the implementation

Records and validation:

1. `Quantity(magnitude=Decimal("1.50"), units="AUD").to_data()["magnitude"] == "1.5"`.
2. `Quantity(magnitude=0.1 + 0.2, units="AUD").magnitude == Decimal("0.3")`.
3. `Quantity(magnitude=1.5, units="m^2").magnitude` is the float `1.5`.
4. A `Decimal` or `str` magnitude in `m^2` fails with `currency_amount`.
5. `Decimal("1234567890.123456")` in `AUD` fails with `amount_digits`.
6. NaN, infinity and `bool` fail in every unit.
7. `Decimal("-0")` in `AUD` gives `"0"`.
8. `kAUD` fails, and the suggestion is `AUD`.
9. A Flow in `AUD` with a float Movement magnitude in its data fails with
   `currency_amount`.

Boundaries:

10. For 10⁵ random amounts with at most 15 significant digits,
    `to_amount(to_number(a)) == a`.
11. `to_amount(float("nan"))` raises `NumericalError`.
12. `Flow.total()` of three `0.10 AUD` movements is `Decimal("0.3")`.
13. `Flow.total()` and the Stream sum of the same Flow give the same amount.
14. `trim`, `clean`, `clone` and `negate` keep each amount with `exact_equal`.
15. A solved Run has the `rangekeeper.money` convention Implementation.
16. A solved Run copies each assigned amount without change. Acceptance
    compares it exactly.
17. A residual of `3.2e-11` in `AUD` is recorded as `"0.000000000032"`.

Encodings:

18. JSON: `"magnitude": 1.5` for an `AUD` Quantity fails. `"1.50"` fails, and the
    error gives `"1.5"`.
19. YAML: `magnitude: 1250000.50` and `magnitude: "1250000.5"` give the same
    record. The writer emits `"1250000.5"`.
20. JSON, YAML and Bundle round trips of a Model with currency, rate and
    geometry magnitudes satisfy `exact_equal`.
21. The Parquet `decimal` field holds canonical text, and DuckDB can cast it
    to `DECIMAL(38, 10)`.
22. The generated JSON Schema accepts `"1.5"` and `1.5` for a magnitude and
    rejects `"1.50"`, `"-0"` and `"1e3"`.
23. The C# fixtures round-trip currency amounts as `System.Decimal`.

Rounding:

24. `round()` of `0.125 AUD` gives `0.12`; with `mode=ROUND_HALF_UP` it gives
    `0.13`.
25. The default places are 0 for `JPY`, 3 for `KWD` and 4 for `CLF`.
26. `round()` of an `XAU` amount without `places` fails; with `places=3` it
    works.
27. `round()` of an `AUD/m^2` Quantity fails.
28. No IO, calculation or record construction changes an amount to its minor
    unit.

Performance:

29. A benchmark of `Flow.from_events` with 120 currency movements stays within
    10 % of the float64 baseline.

## Alternatives and consequences

- **All magnitudes Decimal.** Each slot would have one type, and the type would
  not depend on the units. Rejected: only currency amounts need exact decimals
  and minor units. Geometry and rates come from calculations, so Decimal would
  add conversions with no benefit. As a consequence, a magnitude's type depends
  on its units, and record validation checks the pairing.
- **Currency dimension, including rates.** `AUD/m^2` and `AUD/year` would be
  Decimal. Rejected: rates are calculation inputs and have no minor unit.
- **A separate money type.** Rejected: `Quantity` already has units, and the
  unit registry already knows the currencies. A second type would double the
  API.
- **Shortest round-trip conversion.** This keeps each float64 result exactly.
  Rejected: records would show binary noise, such as `0.30000000000000004`,
  until a user rounds them.
- **Exact Decimal sums for Flow operations.** Rejected: `Flow.total()` and the
  Stream sum could then differ in the last digit.
- **JSON numbers with exact text.** Rejected: a reader that parses numbers as
  doubles loses digits without an error.
- **Parquet `decimal128(38, 18)`.** Native SQL sums would work without a cast.
  Rejected: it needs a limited range and a fixed scale, so a small residual
  would lose digits.
- **Rounding half away from zero by default.** It matches Excel `ROUND`.
  Rejected as the default, because it is biased over many values. It stays
  available as `ROUND_HALF_UP`.
- **Scaled currency units, such as `kAUD`, stored as float.** Rejected: money
  could become float without notice.

Breaking changes for users, all in the 1.0.0 format reset
([#118](https://github.com/daniel-fink/rangekeeper/issues/118),
[#119](https://github.com/daniel-fink/rangekeeper/issues/119)):

- Currency magnitudes are JSON and YAML strings, and Python `Decimal` values.
- Code that does arithmetic on `Quantity.magnitude` in currency units uses
  `number` or the helpers.
- `Settings.relative_tolerance` and `Settings.time_limit` become `double`.
- `ImplementationKind` gets `convention`. Fingerprints change.

Work for other issues:

- #149: no scaled currency units; an ISO 4217 minor unit for each code.
- ADR-011 validation: the codes `currency_amount` and `amount_digits`.
- The C# example generator: `Amount` to `System.Decimal`, `double` to `double`.
- The glossary: the terms currency amount, canonical text and boundary
  conversion.
- #117 stays open for the implementation.

## Sources and related decisions

- [ADR-017: Public API, stability and data formats](017-api-and-formats.md#money):
  this record gives the design of its Money section.
- [ADR-008: Bundle contract](008-rangekeeper-bundle-contract.md) and
  [ADR-011: records and validation](011-records-and-validation.md).
- [ADR-010: layers and packages](010-layers-and-packages.md),
  [ADR-013: execution](013-execution-and-extensions.md) and
  [ADR-016: safety defaults](016-safety-defaults.md).
- [Measurements for this record](../research/decimal-money-2026-10-27/README.md).
- Issues [#117](https://github.com/daniel-fink/rangekeeper/issues/117) and
  [#149](https://github.com/daniel-fink/rangekeeper/issues/149).

Supersedes: none. Superseded by: none.
