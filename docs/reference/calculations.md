# Calculations, Flow and calendar contracts

Known-data calculations consume immutable records and return new records or explicit
results. A Flow records ordered movements with units. It does not declare whether
those movements mean stock, income, rate or balance; the model and chosen operation
define that meaning.

## Flow semantics and explicit operations

A `Movement` has a UUID, optional matching key, magnitude and date or bounded Period. Its date
records a payment or observation; its Period records coverage. Both may be present
and need not coincide. Magnitude `None` is unresolved; zero is an observed amount.
Nonfinite numbers are invalid. Omission and explicit null survive canonical codecs.

`movement.number` returns a finite float or raises for unresolved content.
`movement.coordinate` supplies the alignment coordinate; it does not use the UUID. `movement.resolve(timing=)`
uses the recorded date or an explicit convention for period-only content.
`flow.check(resolved=True)` checks arithmetic readiness and returns the same Flow.
`flow.clean()` removes unresolved movements explicitly; it does not fill them with
zero. These operations have different purposes and never repair content silently.

```python
from datetime import date
from rangekeeper.model.flow import Flow

flow = Flow.from_events([date(2026, 1, 1)], [100], units="AUD")
assert flow.check(resolved=True).movements[0].number == 100.0
assert flow.scale(2).total().magnitude == 200
```

A Flow owns conversion, scaling, negation, totals, trimming, differences, collapse
and extent. Multi-Flow operations live in `calculations.series`: `align`, `aggregate`,
`multiply`, resampling and integration. `Alignment` owns aligned reduction;
`Aggregation` returns its Flow with contribution metadata. Join and missing-data
policies are explicit. A coordinate absent from one input is distinct from a
movement whose magnitude is unresolved. A requested absent zero stays zero in the
destination unit, including conversion between affine units.

Dimensional compatibility is necessary but does not prove the intended economics.
The caller chooses additive totals, weighted means, integration or compounding.
Recorded Claims survive supported operations; derived results retain their declared
contribution boundaries. See [record methods](records.md).

## Calendar and numerical ownership

| Owner | Responsibility |
| --- | --- |
| `model.duration` | Native Gregorian dates, Period coverage, explicit frequencies and timing |
| `Period.check()` / `.resolve()` | Valid coverage and a declared representative date |
| `Distribution` | Canonical parameters and intrinsic `check`, `sample`, `cdf`, `mass` |
| `calculations.projection` | Project a known Quantity over explicit periods |
| `calculations.series` | Align and combine several Flows with explicit policies |
| `calculations.account.Account.calculate` | Interest, overdraft and balance recurrence |
| `calculations.financial` | PV, XNPV, IRR and day counts using PyXIRR |
| `calculations.dynamics` | Deterministic kernels over supplied shocks or samples |
| `model.formulation` | Build declared equations for forward and inverse investigations |

Dates are calendar values, never implicit timestamps. Periods are half-open:
`[start_inclusive, end_exclusive)`. Financial valuation uses actual payment dates; period-only movements
need `PeriodTiming.FIRST`, `PeriodTiming.END` or `PeriodTiming.LAST`. Frequency and elapsed time are
explicit. Currency and time units are not stripped from quantities.

`Distribution.sample(size=..., generator=...)` requires an explicit random
generator. Scenario plans own seed-based stream construction. Distribution algorithms load SciPy only when needed. Financial valuation
can use the smaller `financial` extra without a dataframe or SciPy import.

## Detached tables and plots

The [table reference](tables.md) owns lossless Flow-to-Polars conversion,
`_present` metadata, detached date projections and textual CSV rules. These
projections do not change the Model. Plot adapters return figures so callers
choose display and storage.

## Movement naming

The current API is `Movement` and `Flow.movements`. Old `Sample`, pandas containers,
free functions for intrinsic Flow operations and old duration namespaces have no
compatibility aliases. Use the [upgrade guide](../guides/upgrading.md) when porting
an older consumer. Schema fields and generated records are described in the
[schema guide](../contributing/schema.md); the [walkthroughs](../guides/walkthroughs.md)
show complete calculations and investigations.

## Movement identity

The [identity contract](identity.md#movement-identity-and-alignment) owns Movement
UUID retention and creation. Coordinate alignment does not use UUIDs. Clone a
Flow before placing an independent copy under a second Value.

## Alignment and reduction

`series.align(flows, join=..., missing=...)` returns `Alignment`, which retains
aligned Flows, original known-value coverage and the selected missing policy.
`Alignment.reduce(reducer=AggregationReducer.SUM, units=...)` shares unit conversion,
Claim collection and coverage calculation. `series.aggregate(...)` combines these
two steps. Each reduction returns `Aggregation(flow, coverage)`.

`AlignmentJoin.EXACT` is the default. `UNION` and `INTERSECTION` are explicit.
Missing choices use `MissingValueHandling`; reducer choices use `AggregationReducer`. Zero filling
applies to absent coordinates; an explicitly unresolved movement remains unresolved.
Skip can reduce a partly known group; an entirely unknown group remains unresolved.
Coverage reports the original known fraction, including after zero filling.

`series.multiply`, `integrate` and `resample` retain explicit calculation contracts.
`Account.calculate(...)` returns opening, closing, overdraft and interest Flows.
Financial valuation remains in `calculations.financial`, with explicit timing and
PyXIRR conventions. Calendar grids remain in `model.duration.period`.

## Composed account conventions

Import `Balance`, `CurrentInterest` and `InterestTreatment` from
`rangekeeper.calculations.account`. The numerical calculation and passive schedule use the same
three choices. `Balance.OPENING` selects the signed debt before transactions;
`CLOSING` selects it after transactions. `CurrentInterest.EXCLUDED` charges the
positive selected principal at the per-step rate. `INCLUDED` solves the charge as
`base * rate / (1 - rate)` and requires a rate below one.

`InterestTreatment.SEPARATE` leaves interest out of closing principal; `FINANCED`
adds it. Included current interest requires financing, so six combinations are
valid. The default is closing, excluded, separate. The recurrence retains signed
balances; displayed debt and overdraft balances retain their separate meanings.
Rate Flow coordinates must match transaction coordinates and order. Validation also
applies to empty transactions. Same-day keys never reorder transaction/rate pairs.

`model.formulation.account.schedule` declares the same finite account mechanics with
explicit starting balance, rate, transactions, closing and interest references.
It requires a nonnegative-principal contract. Fixed rate bounds are ordinary
predicates and are checked exactly. Unknown rates and piecewise overdraft branches
remain unsupported. `account.interest` handles explicitly selected principal only.

## Calendar choices

`Frequency` owns the ten supported steps. `model.duration.offset`, `measure`, `align`,
`cover`, `make_period`, `make_periods` and `periods_between` use native dates.
Month offsets default to `MonthRoll.PRESERVE_END`; `CLAMP` is explicit. These rules
are independent of the Period wire-field migration. `DayCount` owns supported
financial year fractions; imported PyXIRR constants remain an adapter detail.
Closed Python API choices require enum members. Wire codecs continue to use text.

## Timing, integration and valuation

`Flow.from_periods` stores coverage only unless `dates=` supplies independent
payment or observation dates. `collapse` requires `on=` or a timing convention
unless the final movement records a date. Trimming keeps whole covered periods
and rejects partial overlap. Resampling groups coverage into a complete target
Period grid and produces period aggregates without payment dates. Keep the
original Flow when individual payment facts are required.

Rate-to-amount conversion needs an exposure. Multiplying `AUD/year` by a
dimensionless factor leaves `AUD/year`; multiplying two rates retains both time
dimensions. `series.integrate` accepts explicit exposure Quantities or a `DayCount`
member for bounded periods:

```python
from datetime import date
from rangekeeper.model.duration import DayCount, Frequency, make_periods
from rangekeeper.model.flow import Flow
from rangekeeper.calculations import series

periods = make_periods(date(2026, 1, 1), frequency=Frequency.MONTH, count=3)
rates = Flow.from_periods(periods, (120, 120, 120), units="AUD/year")
amounts = series.integrate(rates, day_count=DayCount.ACTUAL_365, units="AUD")
assert abs(amounts.total().magnitude - 120 * 90 / 365) < 1e-9
```

The caller selects last for a closing balance, sum for receipts, or mean with
explicit weighting. The library does not infer this from a Flow kind. Bounded
movements crossing target periods must be allocated first. Resampling coverage
counts known observations, not continuous time coverage. Zero filling does not
resolve an explicitly unknown observation.

`calculate_pv` uses a per-observation rate and explicit `first_period` index.
`calculate_xnpv` uses a valuation date and day-count convention; `calculate_irr`
returns one PyXIRR root and its residual. Both require `timing=` for period-only
movements. `IrrResult` contains `rate`, `residual`, `guess` and
`method="pyxirr.xirr"`. A guess is neither a bound nor proof of root uniqueness.
Failed or nonfinite library results raise `ValueError`. An IRR residual greater
than `1e-8 * max(gross_movements, 1)` also fails. Empty Flows have zero XNPV but no
IRR. There is no bounded-solver fallback.
